"""Run one discrete Freeway episode with token-reveal time pressure.

The runner owns the episode loop, the reveal schedule, and the actor
context string. Time pressure is how many new reasoning tokens are
appended each environment step, not wall-clock delay. The actor never
sees `context_mode`; this module chooses what to put in `context`.

Usage from the repository root (no Ollama in offline tests):

    python -m decision_model_experiments.experiment_runner --help
    python -m decision_model_experiments.experiment_runner \\
        --context-mode observation --log-path logs/observation_episode.json
    python -m decision_model_experiments.experiment_runner \\
        --context-mode reasoning --observer-tokens 10 --time-pressure 3 \\
        --log-path logs/reasoning_episode.json
    python -m decision_model_experiments.experiment_runner \\
        --context-mode both --observer-tokens 10 --time-pressure 3 \\
        --log-path logs/both_episode.json

The pygame Freeway window is on by default. Pass `--no-render` for a
headless run (offline tests always stay headless). The installed
RealtimeGym wheel has no sprite assets, so the window is drawn from
`env.pos` / `env.cars` rather than `FreewayRender`.

Inputs: CLI settings, a local Ollama model, and live Freeway observations.
Output: one JSON file per episode (`logs/decision_model_*.json` by default).
`--log-path` refuses to overwrite an existing file.

`observation` is one `act`/`step` per current state and never calls the
observer. `reasoning` / `both` call `observer.think` once per trace, then
reveal `time_pressure` tokens per step until that trace is exhausted or
the episode ends. Inner-loop length uses the actual token count, so a
short or empty observer reply does not invent extra steps. `x` and
`time_pressure` are ignored in `observation` and logged as unused.

`TOKENIZATION_METHOD` is the named approximation (`whitespace`) used
because model tokenization is unavailable offline; record this name in
the episode log and do not switch methods across runs.
`OBSERVATION_FRESHNESS` is the locked inner-loop policy (`live`).

Tests: `python -m unittest tests.test_experiment_runner -v`
"""

import argparse
import copy
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

from decision_model_experiments.actor_agent import FALLBACK_ACTION, ActorAgent
from decision_model_experiments.models import (
    DEFAULT_REASONING_MODEL,
    ModelClient,
    ModelConfig,
    post_json,
)
from decision_model_experiments.observer_agent import ObserverAgent


# Named approximation, not Qwen/Ollama tokens. Model tokenization would
# require a live Ollama call; using it only when reachable would silently
# switch methods across machines. Keep this name fixed and log it.
TOKENIZATION_METHOD = "whitespace"


def tokenize_reasoning(trace, method=TOKENIZATION_METHOD):
    """Split an observer trace with the named method. Empty text is zero tokens."""
    if method != TOKENIZATION_METHOD:
        raise ValueError(
            f"unknown tokenization method {method!r}; "
            f"record {TOKENIZATION_METHOD!r} in the episode log"
        )
    return str(trace).split()


def count_reasoning_tokens(trace, method=TOKENIZATION_METHOD):
    """Return the actual token count of one observer trace."""
    return len(tokenize_reasoning(trace, method=method))


def reveal_prefix_lengths(token_count, time_pressure):
    """Prefix lengths for `ceil(actual_token_count / time_pressure)` steps.

    Example: 10 tokens and pressure 3 → (3, 6, 9, 10). Zero tokens → no steps.
    """
    if time_pressure <= 0:
        raise ValueError("time_pressure must be a positive token count")
    if token_count < 0:
        raise ValueError("token_count cannot be negative")
    if token_count == 0:
        return []
    n_chunks = math.ceil(token_count / time_pressure)
    return [
        min((index + 1) * time_pressure, token_count)
        for index in range(n_chunks)
    ]


def join_reasoning_tokens(tokens, method=TOKENIZATION_METHOD):
    """Rebuild a revealed prefix from tokens using the same named method."""
    if method != TOKENIZATION_METHOD:
        raise ValueError(
            f"unknown tokenization method {method!r}; "
            f"record {TOKENIZATION_METHOD!r} in the episode log"
        )
    return " ".join(tokens)


def revealed_reasoning_prefixes(trace, time_pressure, method=TOKENIZATION_METHOD):
    """Successive revealed prefixes of the observer trace.

    Each step appends up to `time_pressure` new tokens. The last prefix is the
    full actual trace, which may be shorter than the observer generation budget.
    """
    tokens = tokenize_reasoning(trace, method=method)
    lengths = reveal_prefix_lengths(len(tokens), time_pressure)
    return [join_reasoning_tokens(tokens[:length], method=method) for length in lengths]


# Locked inner-loop policy: `both` (and `observation`) use the state the
# runner passes in, which is the live env observation after previous steps.
# Do not add a frozen-snapshot argument; the observer's original view stays
# out of actor context unless the caller passes that same dict as `observation`.
OBSERVATION_FRESHNESS = "live"
CONTEXT_MODES = ("reasoning", "observation", "both")
REVEALED_REASONING_LABEL = "Revealed reasoning:"
OBSERVATION_LABEL = "Observation:"


def convert_scalar(value):
    # Observations can contain NumPy scalars; JSON needs plain Python values.
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def format_observation_text(observation, board="full"):
    """Serialize a raw Freeway observation for actor context."""
    if isinstance(observation, str):
        return observation
    snapshot = copy.deepcopy(observation)
    if board == "structured" and isinstance(snapshot, dict):
        snapshot.pop("state_string", None)
    return json.dumps(snapshot, default=convert_scalar)


def build_actor_context(context_mode, revealed, observation, board="full"):
    """Assemble the condition-specific string `ActorAgent.act` receives.

    The actor does not know `context_mode`. Unused inputs are omitted:
    `observation` mode drops `revealed`; `reasoning` mode drops `observation`.
    `both` concatenates the revealed prefix and the live observation so the
    actor can notice that the world moved after the observer thought.
    """
    if context_mode not in CONTEXT_MODES:
        raise ValueError(
            f"unknown context_mode {context_mode!r}; "
            f"expected one of {CONTEXT_MODES}"
        )
    parts = []
    if context_mode in ("reasoning", "both"):
        parts.append(f"{REVEALED_REASONING_LABEL}\n{revealed}")
    if context_mode in ("observation", "both"):
        # Format only when this mode shows the env state, so a live dict
        # passed during `reasoning` cannot leak into the actor context.
        parts.append(
            f"{OBSERVATION_LABEL}\n"
            f"{format_observation_text(observation, board=board)}"
        )
    return "\n\n".join(parts)


def generation_result_fields(result):
    """Serialize a GenerationResult so failed requests stay in the JSON log."""
    if result is None:
        return None
    return {
        "prompt": result.prompt,
        "max_tokens": result.max_tokens,
        "think": result.think,
        "payload": result.payload,
        "response": result.response,
        "error": result.error,
        "content": result.content,
        "thinking": result.thinking,
        "done_reason": result.done_reason,
        "output_tokens": result.output_tokens,
        "input_tokens": result.input_tokens,
        "latency_seconds": result.latency_seconds,
    }


def unused_reasoning_from_trace(trace, revealed_token_count, method=TOKENIZATION_METHOD):
    """Unrevealed suffix and its token count after a prefix has been shown."""
    tokens = tokenize_reasoning(trace, method=method)
    leftover_count = max(len(tokens) - revealed_token_count, 0)
    leftover_text = join_reasoning_tokens(tokens[revealed_token_count:], method=method)
    return leftover_text, leftover_count


FREEWAY_WINDOW_COLS = 9
FREEWAY_WINDOW_ROWS = 10
FREEWAY_WINDOW_CELL = 48


def draw_freeway_surface(env, cell_size=FREEWAY_WINDOW_CELL):
    """Draw the current Freeway grid without RealtimeGym sprite files."""
    import pygame
    if not pygame.get_init():
        pygame.init()
    width = FREEWAY_WINDOW_COLS * cell_size
    height = FREEWAY_WINDOW_ROWS * cell_size
    surface = pygame.Surface((width, height))
    grass = (62, 140, 72)
    road = (72, 72, 78)
    lane_line = (230, 230, 230)
    crossing = (210, 190, 60)
    car_right = (200, 70, 60)
    car_left = (70, 110, 200)
    player = (250, 220, 70)
    for row in range(FREEWAY_WINDOW_ROWS):
        for col in range(FREEWAY_WINDOW_COLS):
            rect = pygame.Rect(col * cell_size, row * cell_size, cell_size, cell_size)
            if row in (0, FREEWAY_WINDOW_ROWS - 1):
                surface.fill(grass, rect)
            elif col == 4:
                surface.fill(crossing, rect)
            else:
                surface.fill(road, rect)
            if row not in (0, FREEWAY_WINDOW_ROWS - 1) and col < FREEWAY_WINDOW_COLS - 1:
                pygame.draw.line(
                    surface, lane_line,
                    ((col + 1) * cell_size, row * cell_size),
                    ((col + 1) * cell_size, (row + 1) * cell_size),
                    1,
                )
    for car in getattr(env, "cars", []) or []:
        if len(car) < 5:
            continue
        x, y, _timer, speed, length = car[:5]
        if x is None or speed is None or y is None or length is None:
            continue
        going_right = speed > 0
        car_y = int(y) * cell_size
        if going_right:
            car_x = (int(x) - int(length) + 1) * cell_size
        else:
            car_x = int(x) * cell_size
        car_rect = pygame.Rect(car_x, car_y, int(length) * cell_size, cell_size)
        pygame.draw.rect(surface, car_right if going_right else car_left, car_rect)
        pygame.draw.rect(surface, (20, 20, 20), car_rect, 1)
    pos = getattr(env, "pos", None)
    if pos is not None:
        center = (
            4 * cell_size + cell_size // 2,
            int(pos) * cell_size + cell_size // 2,
        )
        pygame.draw.circle(surface, player, center, max(cell_size // 3, 8))
        pygame.draw.circle(surface, (20, 20, 20), center, max(cell_size // 3, 8), 2)
    font = pygame.font.Font(None, 28)
    turn = getattr(env, "game_turn", "?")
    score = getattr(env, "reward", "")
    info = font.render(f"Turn {turn}  Score {score}", True, (255, 255, 255))
    background = info.get_rect()
    background.topleft = (8, 8)
    pygame.draw.rect(surface, (0, 0, 0), background.inflate(10, 6))
    surface.blit(info, background)
    if getattr(env, "terminal", False):
        overlay = pygame.Surface((width, height))
        overlay.set_alpha(120)
        overlay.fill((0, 0, 0))
        surface.blit(overlay, (0, 0))
        end_text = "SUCCESS" if int(getattr(env, "game_turn", 100)) < 100 else "GAME OVER"
        end = pygame.font.Font(None, 48).render(end_text, True, (255, 255, 255))
        end_rect = end.get_rect(center=(width // 2, height // 2))
        surface.blit(end, end_rect)
    return surface


class FreewayPygameWindow:
    """Live pygame window for one episode. Missing sprites are not required."""

    def __init__(self, title="Freeway"):
        import pygame
        pygame.init()
        pygame.display.init()
        self._pygame = pygame
        self.screen = pygame.display.set_mode(
            (FREEWAY_WINDOW_COLS * FREEWAY_WINDOW_CELL,
             FREEWAY_WINDOW_ROWS * FREEWAY_WINDOW_CELL),
        )
        pygame.display.set_caption(title)
        self.closed = False

    def draw(self, env):
        if self.closed:
            return
        pygame = self._pygame
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.close()
                    return
            self.screen.blit(draw_freeway_surface(env), (0, 0))
            pygame.display.flip()
        except pygame.error:
            self.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self._pygame.display.quit()
        except Exception:
            pass


def _open_freeway_window(title="Freeway"):
    return FreewayPygameWindow(title)


def _make_freeway(seed):
    # Always headless at the RealtimeGym layer. The installed package has no
    # sprite assets, so FreewayRender raises FileNotFoundError on chicken.png.
    import realtimegym
    return realtimegym.make("Freeway-v0", seed=seed, render=False)


def _reached_goal(done, steps):
    # Moving up from y=8 reaches the goal, including on the last turn.
    last_step = steps[-1] if steps else None
    if not (done and last_step and last_step["action"] == "U"):
        return False
    before = last_step.get("observation_before") or {}
    state = before.get("state") or {}
    return state.get("player_states") == 8


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Run one Freeway episode where the actor sees observer reasoning, "
            "the current observation, or both."
        ),
    )
    parser.add_argument(
        "--context-mode",
        choices=CONTEXT_MODES,
        required=True,
        help="Actor context condition: reasoning, observation, or both.",
    )
    parser.add_argument(
        "--time-pressure",
        type=int,
        default=8,
        help="New reasoning tokens revealed per environment step (unused in observation).",
    )
    parser.add_argument(
        "--observer-tokens",
        "-x",
        type=int,
        default=256,
        dest="observer_tokens",
        help="Observer generation budget x (unused in observation). "
             "With thinking on, this budget is spent on thinking first.",
    )
    parser.add_argument("--seed", type=int, choices=range(8), default=0)
    parser.add_argument("--model", default=DEFAULT_REASONING_MODEL)
    parser.add_argument("--model-seed", type=int, default=0, dest="model_seed")
    parser.add_argument(
        "--thinking",
        choices=["off", "on"],
        default="on",
        help="Observer thinking only; unused in observation. Actor thinking stays off.",
    )
    parser.add_argument("--board", choices=["full", "structured"], default="full")
    parser.add_argument(
        "--render",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show the pygame Freeway window while the episode runs.",
    )
    parser.add_argument(
        "--log-path",
        default=None,
        dest="log_path",
        help="JSON output path. Refuses to overwrite an existing file.",
    )
    return parser


def parse_args(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.log_path and Path(args.log_path).exists():
        parser.error("log path already exists; choose a new filename")
    if args.time_pressure <= 0 or args.observer_tokens <= 0:
        parser.error("time pressure and observer tokens must be positive")
    return args


class ExperimentRunner:
    """Own the mode-specific Freeway loop and write one JSON episode log."""

    def __init__(self, observer, actor, args):
        self.observer = observer
        self.actor = actor
        self.args = args
        self._window = None

    def run(self):
        args = self.args
        log_path = self._resolve_log_path()
        unused_in_observation = args.context_mode == "observation"
        episode = {
            "environment": "Freeway-v0",
            "requested_seed": args.seed,
            "real_seed": None,
            "settings": {
                "model": args.model,
                "seed": args.seed,
                "model_seed": args.model_seed,
                "observer_tokens": args.observer_tokens,
                "time_pressure": args.time_pressure,
                "context_mode": args.context_mode,
                "observation_freshness": OBSERVATION_FRESHNESS,
                "tokenization_method": TOKENIZATION_METHOD,
                "observer_tokens_unused": unused_in_observation,
                "time_pressure_unused": unused_in_observation,
                "thinking": args.thinking,
                "thinking_unused": unused_in_observation,
                "board": args.board,
                "fallback_action": FALLBACK_ACTION,
                "actor_thinking": False,
                "render": bool(getattr(args, "render", False)),
                "log_path": str(log_path),
            },
            "model_metadata": None,
            "warmup": None,
            "initial_observation": None,
            "observer_cycles": [],
            "steps": [],
            "summary": None,
        }
        error = None
        env = None
        done = False
        collisions = 0
        self._window = None
        unused_reasoning = ""
        unused_reasoning_tokens = 0
        x_label = f"x={args.observer_tokens}"
        pressure_label = f"time_pressure={args.time_pressure}"
        if unused_in_observation:
            x_label += " (unused)"
            pressure_label += " (unused)"
        print(
            f"Starting Freeway episode | mode {args.context_mode} | "
            f"{x_label} | {pressure_label}",
            flush=True,
        )
        try:
            # Metadata and warmup happen before reset so their latency is not
            # mixed into the first think/act, and so a missing model fails first.
            episode["model_metadata"] = post_json("show", {"model": args.model})
            episode["warmup"] = self._warmup()
            env, real_seed, _ = _make_freeway(args.seed)
            episode["real_seed"] = int(real_seed)
            if getattr(args, "render", False):
                self._window = _open_freeway_window(
                    f"Freeway | {args.context_mode}",
                )
            observation, done = env.reset()
            episode["initial_observation"] = copy.deepcopy(observation)
            self._draw_env(env)
            if args.context_mode == "observation":
                collisions, done = self._run_observation_loop(
                    env, episode, observation, done,
                )
            else:
                (
                    collisions,
                    done,
                    unused_reasoning,
                    unused_reasoning_tokens,
                    loop_error,
                ) = self._run_reveal_loop(env, episode, observation, done)
                error = loop_error
        except BaseException as exception:
            error = f"{type(exception).__name__}: {exception}"
            raise
        finally:
            turns = int(env.game_turn) if env is not None else 0
            final_score = float(env.reward) if env is not None else None
            episode_ended = bool(done)
            episode["summary"] = {
                "episode_ended": episode_ended,
                "turns": turns,
                "collisions": collisions,
                "final_score": final_score,
                "success": _reached_goal(episode_ended, episode["steps"]),
                "unused_reasoning_tokens": unused_reasoning_tokens,
                "unused_reasoning": unused_reasoning,
                "observer_call_count": len(episode["observer_cycles"]),
                "error": error,
            }
            self._write_log(log_path, episode)
            print("\nEpisode log saved to:", log_path, flush=True)
            if env is not None:
                self._draw_env(env)
            self._close_window()
        if env is not None:
            env.summary()
        return episode

    def _resolve_log_path(self):
        if self.args.log_path:
            log_path = Path(self.args.log_path).resolve()
            if log_path.exists():
                raise FileExistsError(
                    f"log path already exists; choose a new filename: {log_path}"
                )
            log_path.parent.mkdir(parents=True, exist_ok=True)
            return log_path
        log_directory = Path(__file__).resolve().parents[1] / "logs"
        log_directory.mkdir(exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return log_directory / f"decision_model_{timestamp}.json"

    def _warmup(self):
        payload = {
            "model": self.args.model,
            "messages": [{"role": "user", "content": "Return only S."}],
            "think": False,
            "stream": False,
            "keep_alive": "5m",
        }
        started = time.perf_counter()
        try:
            response = post_json("chat", payload)
            error = None
        except Exception as exception:
            response = None
            error = f"{type(exception).__name__}: {exception}"
        return {
            "request": payload,
            "response": response,
            "error": error,
            "latency_seconds": time.perf_counter() - started,
        }

    def _write_log(self, log_path, episode):
        with log_path.open("w", encoding="utf-8") as file:
            json.dump(episode, file, indent=2, default=convert_scalar)

    def _run_observation_loop(self, env, episode, observation, done):
        # Reactive baseline: never think, never reveal, one action per state.
        collisions = 0
        while not done:
            context = build_actor_context(
                "observation", "", observation, board=self.args.board,
            )
            observation, done, collisions = self._act_and_step(
                env,
                episode,
                observation,
                context,
                revealed_token_count=0,
                observer_cycle_id=None,
                collisions=collisions,
            )
        return collisions, done

    def _run_reveal_loop(self, env, episode, observation, done):
        collisions = 0
        unused_reasoning = ""
        unused_reasoning_tokens = 0
        while not done:
            snapshot = copy.deepcopy(observation)
            reasoning = self.observer.think(observation)
            result = self.observer.last_result
            token_count = count_reasoning_tokens(reasoning)
            lengths = reveal_prefix_lengths(token_count, self.args.time_pressure)
            prefixes = revealed_reasoning_prefixes(
                reasoning, self.args.time_pressure,
            )
            cycle_id = len(episode["observer_cycles"])
            episode["observer_cycles"].append({
                "id": cycle_id,
                "observation": snapshot,
                "reasoning": reasoning,
                "token_count": token_count,
                "tokenization_method": TOKENIZATION_METHOD,
                "prefix_lengths": lengths,
                "latency_seconds": None if result is None else result.latency_seconds,
                "output_tokens": None if result is None else result.output_tokens,
                "input_tokens": None if result is None else result.input_tokens,
                "error": None if result is None else result.error,
                "generation": generation_result_fields(result),
            })
            print(
                f"Observer cycle {cycle_id} | tokens {token_count} | "
                f"prefixes {len(prefixes)}",
                flush=True,
            )
            # An empty trace has been fully revealed. Do not invent act/step
            # cycles, and do not immediately re-think forever.
            unused_reasoning, unused_reasoning_tokens = unused_reasoning_from_trace(
                reasoning, 0,
            )
            if not prefixes:
                return (
                    collisions,
                    done,
                    unused_reasoning,
                    unused_reasoning_tokens,
                    "empty observer trace produced no reveal steps",
                )
            for prefix, length in zip(prefixes, lengths):
                unused_reasoning, unused_reasoning_tokens = unused_reasoning_from_trace(
                    reasoning, length,
                )
                context = build_actor_context(
                    self.args.context_mode,
                    prefix,
                    observation,
                    board=self.args.board,
                )
                observation, done, collisions = self._act_and_step(
                    env,
                    episode,
                    observation,
                    context,
                    revealed_token_count=length,
                    observer_cycle_id=cycle_id,
                    collisions=collisions,
                )
                if done:
                    break
        return collisions, done, unused_reasoning, unused_reasoning_tokens, None

    def _act_and_step(
        self,
        env,
        episode,
        observation,
        context,
        revealed_token_count,
        observer_cycle_id,
        collisions,
    ):
        action = self.actor.act(context)
        source = self.actor.last_action_source or "fallback"
        before = copy.deepcopy(observation)
        observation_after, done, score, collided = env.step(action)
        collisions += int(collided)
        episode["steps"].append({
            "turn": int(env.game_turn),
            "revealed_token_count": revealed_token_count,
            "context_mode": self.args.context_mode,
            "context": context,
            "action": action,
            "source": source,
            "score": float(score),
            "collision": bool(collided),
            "done": bool(done),
            "observer_cycle_id": observer_cycle_id,
            "observation_before": before,
            "observation_after": copy.deepcopy(observation_after),
            "actor_result": generation_result_fields(self.actor.last_result),
        })
        print(
            f"Turn {env.game_turn:3d} | {action} | {source} | "
            f"revealed {revealed_token_count} | "
            f"Score {score} | Collision {collided}",
            flush=True,
        )
        self._draw_env(env)
        return observation_after, bool(done), collisions

    def _draw_env(self, env):
        # Live window only. Closing it stops drawing; the episode still logs.
        if self._window is None:
            return
        self._window.draw(env)
        if getattr(self._window, "closed", False):
            self._window = None

    def _close_window(self):
        if self._window is None:
            return
        close = getattr(self._window, "close", None)
        if close is not None:
            close()
        self._window = None


def main(argv=None):
    args = parse_args(argv)
    client = ModelClient(
        ModelConfig(reasoning_model=args.model, seed=args.model_seed),
    )
    observer = ObserverAgent(
        client,
        max_tokens=args.observer_tokens,
        thinking=args.thinking == "on",
        board=args.board,
    )
    actor = ActorAgent(client)
    return ExperimentRunner(observer, actor, args).run()


if __name__ == "__main__":
    main()