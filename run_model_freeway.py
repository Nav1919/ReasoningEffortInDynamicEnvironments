"""Run one asynchronous Freeway episode using local Ollama.

Usage: python run_model_freeway.py --help (defaults: original/full, thinking off).
Inputs: CLI settings and live observations. Output: timestamped logs/*.json.
Checks: test_model_freeway.py, test_freeway_study.py, test_reproducibility.py;
saved episodes are also verified by replay_freeway.py. See README.md.
"""
# imports
import argparse
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import realtimegym
from reasoning_modes import QWEN_MODES, thinking_value
from experiment_config import validate_config
import hashlib


def convert_scalar(value):
    # observations can contain NumPy scalars
    # turn those into regular Python values before saving or sending JSON
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def post_json(endpoint, payload, timeout=180):
    # send a request to the Ollama server running on our own computer
    request = Request(
        f"http://localhost:11434/api/{endpoint}",
        data=None if endpoint in {"version", "tags"} else json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="GET" if endpoint in {"version", "tags"} else "POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_prompt(observation, tick_seconds, strategy="original", board="full"):
    if strategy == "progress_source_v2":
        # Keep historical templates byte-identical; version the edge-clamp clarification.
        return build_prompt(observation, tick_seconds, "progress_source", board).replace(
            "U increases player y by 1; D decreases it by 1; S leaves it unchanged. ",
            "U increases player y by 1; D decreases it by 1; both clamp at the "
            "start/goal edges. S leaves it unchanged. ")
    # explain the structured state using the benchmark's coordinate system
    # x=0 is the player's column; y=0 is the start and y=9 is the goal
    # this snapshot won't update while the model generates its response
    # Keep the original wording available for exact comparisons.
    # Removing the board is independent of changing the instructions.
    observation = copy.deepcopy(observation)
    if board == "structured":
        observation.pop("state_string", None)
    progress = ""
    if strategy in {"progress", "progress_source"}:
        # Encourage the objective without choosing an action for the model.
        # Staying is still allowed when it helps avoid an imminent collision.
        progress = (
            "Your objective is to CROSS, not to survive at the starting line. "
            "Staying forever loses at turn 100. Make upward progress when possible; "
            "use S or D when traffic makes that useful. S is not automatically safe "
            "in a traffic lane. Choose for the next action opportunity despite "
            "uncertainty; do not wait forever for a perfectly certain crossing.\n"
        )
    prompt = progress + (
        "Play Freeway. Choose one action: U (up), D (down), or S (stay). "
        "Reach y=9 from y=0 while avoiding cars in lanes y=1 through y=8. "
        "U increases player y by 1; D decreases it by 1; S leaves it unchanged. "
        "The player stays at x=0. player_states is player y. "
        "Each car_states entry is [lane_y, head_x, direction, speed, length]. "
        "Positions, speed, and length use units of 1/12 of a board column. "
        "Speed is the positive distance moved per turn. "
        "For right-moving cars the tail is head_x-length; "
        "for left-moving cars it is head_x+length. Cars wrap around the board. "
        "The player moves before cars move and collisions are checked. "
        "A collision resets the player and traffic to their starting layout. "
        "Score starts at 100 and falls by 1 each turn. "
        "The episode ends on reaching the goal or after 100 turns. "
        f"The game advances approximately every {tick_seconds} seconds, "
        "using S while you generate your response. Your snapshot may be stale "
        "when your action is applied. Return only U, D, or S.\n\n"
        "Observation:\n"
        + json.dumps(observation, default=convert_scalar)
    )
    if strategy == "progress_source":
        # This separately named variant corrects the simplified mechanics.
        # The existing original/progress variants remain exactly as before.
        # It is available for later work, not substituted into the matched study.
        prompt = prompt.replace(
            "Speed is the positive distance moved per turn. ",
            "Speed is the nominal positive distance per turn in the structured "
            "encoding. Actual car heads move on integer board cells: slow cars "
            "use timers, and their structured head positions include timer phase. "
        ).replace(
            "Cars wrap around the board. ",
            "A car whose integer head was already outside the nine board columns "
            "at the start of a turn is placed at the opposite edge that turn "
            "without an additional move. Otherwise its timer or speed advances "
            "it. This is not ordinary modulo wrapping. Collisions check the "
            "updated occupied integer cells, not the swept path between cells. "
        ).replace(
            "The player moves before cars move and collisions are checked. ",
            "The player moves first. Reaching y=9 ends immediately before cars "
            "move; otherwise cars move and collisions are checked. "
        ).replace(
            "A collision resets the player and traffic to their starting layout. ",
            "A collision sends the player to y=0. If the episode has not ended, "
            "traffic also resets to its seeded starting layout; elapsed turns "
            "and score are preserved. "
        )
    return prompt


def request_action(payload, probe_delay):
    # this function runs in a worker thread
    # only the main thread touches the environment
    started = time.perf_counter()
    try:
        if probe_delay is not None:
            # this is a clock test, not a model response
            # pretend an agent needs time to decide, then choose U
            time.sleep(probe_delay)
            response = {"message": {"content": "U"}, "done_reason": "stop"}
        else:
            response = post_json("chat", payload)
        error = None
    except Exception as exception:
        # a failed model request shouldn't stop the game clock
        # save the error and fall back to S when this request finishes
        response = None
        error = f"{type(exception).__name__}: {exception}"
    finished = time.perf_counter()
    return response, error, started, finished


def parse_action(response, error=None):
    # Accept only a completed response containing one action, ignoring case
    # and surrounding whitespace. Never extract actions from prose or thinking.
    content = (response or {}).get("message", {}).get("content", "")
    action = content.strip().upper()
    valid = (error is None and (response or {}).get("done_reason") == "stop"
             and action in {"U", "D", "S"})
    return action if valid else None


def prompt_record(config, tick_seconds):
    """Record the exact instruction prefix and a fingerprint, excluding observation."""
    prompt = config['prompt']
    template = build_prompt({}, tick_seconds, prompt['variant'], prompt['board'])
    instructions = template.rsplit('Observation:\n', 1)[0] + 'Observation:\n'
    return dict(**prompt, instruction_template=instructions,
                template_sha256=hashlib.sha256(instructions.encode()).hexdigest())


def build_comparison_request(observation, config, mode, tick_seconds):
    """Build a controlled request; mode may change only Ollama's think field."""
    config = validate_config(config)
    if mode not in config['modes'] or tick_seconds not in config['tick_intervals']:
        raise ValueError('Mode/condition is outside the recorded design')
    prompt = config['prompt']
    return dict(model=config['model']['tag'],
        messages=[{'role':'user', 'content':build_prompt(observation, tick_seconds,
                  prompt['variant'], prompt['board'])}],
        think=thinking_value(config['modes'][mode]), stream=False, keep_alive='5m',
        options=copy.deepcopy(config['generation']))


def build_request(observation, args):
    # Share exactly the same request settings between diagnostics and pilots.
    return {
        "model": args.model,
        "messages": [{"role": "user", "content": build_prompt(
            observation, args.tick_seconds, args.prompt, args.board)}],
        "think": thinking_value(QWEN_MODES[args.thinking]), "stream": False, "keep_alive": "5m",
        "options": {"temperature": 0.6, "seed": getattr(args, "model_seed", 0),
                    "num_predict": 2048, "num_ctx": 4096},
    }


def main():
    # command-line options let us change modes without editing the file
    parser = argparse.ArgumentParser()
    parser.add_argument("--thinking", choices=["off", "on"], default="off")
    parser.add_argument("--tick-seconds", type=float, default=1.0)
    parser.add_argument("--seed", type=int, choices=range(8), default=0)
    parser.add_argument("--model-seed", type=int, default=0)
    parser.add_argument("--model", default="qwen3:4b-q4_K_M")
    parser.add_argument("--probe-delay", type=float, default=None)
    parser.add_argument("--prompt", choices=["original", "progress", "progress_source"], default="original")
    parser.add_argument("--board", choices=["full", "structured"], default="full")
    # A study can choose the output name without parsing console messages.
    # Refuse an existing file so a rerun cannot overwrite earlier evidence.
    parser.add_argument("--log-path", default=None)
    args = parser.parse_args()
    if args.log_path and Path(args.log_path).exists():
        parser.error("log path already exists; choose a new filename")
    if args.tick_seconds <= 0 or (
        args.probe_delay is not None and args.probe_delay < 0
    ):
        parser.error("tick seconds must be positive; probe delay cannot be negative")

    # record the actual model metadata before starting the game clock
    # fail here if Ollama isn't running or the requested model is missing
    # the delayed scripted probe doesn't need Ollama
    model_metadata = None
    if args.probe_delay is None:
        model_metadata = post_json("show", {"model": args.model})

    # Warm up before the clock starts and preserve this request separately.
    # Warm-up latency is never included in episode decision latency.
    warmup = None
    if args.probe_delay is None:
        payload = {"model": args.model, "messages": [{"role": "user",
                   "content": "Return only S."}], "think": False,
                   "stream": False, "keep_alive": "5m"}
        response, warm_error, start, finish = request_action(payload, None)
        warmup = {"request": payload, "response": response, "error": warm_error,
                  "latency_seconds": finish - start}

    env, real_seed, _ = realtimegym.make("Freeway-v0", seed=args.seed, render=False)
    observation, done = env.reset()
    log_directory = Path(__file__).resolve().parent / "logs"
    log_directory.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    log_path = log_directory / f"model_freeway_{timestamp}.json"
    if args.log_path:
        log_path = Path(args.log_path).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
    episode = {
        "environment": "Freeway-v0",
        "requested_seed": args.seed,
        "real_seed": int(real_seed),
        "settings": vars(args),
        "model_metadata": model_metadata,
        "warmup": warmup,
        "policy": "delayed_scripted_probe" if args.probe_delay is not None else "ollama",
        "timing_mode": "wall_clock_with_worker_inference",
        "default_action": "S",
        "initial_observation": copy.deepcopy(observation),
        "decisions": [],
        "steps": [],
    }

    # use one worker and allow only one outstanding request at a time
    # a ready action is applied once, at the next game tick
    worker = ThreadPoolExecutor(max_workers=1)
    pending = None
    decision = None
    ready = None
    collisions = 0
    started_episode = time.perf_counter()
    next_tick = started_episode + args.tick_seconds
    error = None

    def collect_response():
        # collect a completed response without changing the environment
        response, request_error, started, finished = pending.result()
        parsed = parse_action(response, request_error)
        valid = parsed is not None
        decision.update({
            "response": response,
            "error": request_error,
            "latency_seconds": finished - started,
            "request_started_seconds": started - started_episode,
            "response_finished_seconds": finished - started_episode,
            "response_collected_turn": int(env.game_turn),

            # count ticks that happened inside the measured request interval
            # this is stronger evidence than just checking total latency
            "ticks_during_request": sum(
                started - started_episode
                <= step["elapsed_seconds"]
                <= finished - started_episode
                for step in episode["steps"]
            ),
            "valid_action": valid,
            "parsed_action": parsed,
            "fallback_action": None if valid else "S",
            "completion_reason": (response or {}).get("done_reason"),
            "output_tokens": (response or {}).get("eval_count"),
            "input_tokens": (response or {}).get("prompt_eval_count"),
        })

        # reject prose, invalid actions, and truncated responses
        # don't search the thinking text for a letter that looks like an action
        print(
            f"Decision {decision['id']} | saw turn {decision['observed_turn']} | "
            f"collected at turn {env.game_turn} | "
            f"action {decision['parsed_action']} | valid {valid}",
            flush=True,
        )

    try:
        while not done:
            if pending is None and ready is None:
                # freeze a copy of the state the model actually receives
                # later turns won't silently change this saved observation
                observed_seconds = time.perf_counter() - started_episode
                snapshot = copy.deepcopy(observation)
                payload = build_request(snapshot, args)
                decision = {
                    "id": len(episode["decisions"]),
                    "observed_turn": int(env.game_turn),
                    "observation": snapshot,
                    "observed_seconds": observed_seconds,
                    "request": payload,
                    "submitted_seconds": time.perf_counter() - started_episode,
                }
                episode["decisions"].append(decision)
                pending = worker.submit(request_action, payload, args.probe_delay)

            if pending is not None and pending.done():
                collect_response()
                ready = decision
                pending = None

            now = time.perf_counter()
            if now >= next_tick:
                # S is the waiting action even after a previous U or D
                # don't keep repeating the last model action during inference
                action = "S"
                source = "waiting_default"
                if ready is not None:
                    action = ready["parsed_action"] or ready["fallback_action"]
                    source = "model" if ready["valid_action"] else "invalid_fallback"
                if args.probe_delay is not None and ready is not None:
                    source = "probe"
                if ready is not None:
                    # age counts turns already elapsed before applying the action
                    ready["applied_turn"] = int(env.game_turn) + 1
                    ready["observation_age_turns"] = (
                        int(env.game_turn) - ready["observed_turn"]
                    )
                    # Seconds include the wait for tick alignment after a response
                    # is ready. Turn age excludes the action's own environment step.
                    ready["applied_seconds"] = now - started_episode
                    ready["observation_age_seconds"] = (
                        ready["applied_seconds"] - ready["observed_seconds"]
                    )
                    ready["executed_action"] = action
                    ready["status"] = "applied"

                before = copy.deepcopy(observation)
                previous_score = float(env.reward)
                observation, done, score, collided = env.step(action)
                collisions += int(collided)
                episode["steps"].append({
                    "turn": int(env.game_turn),
                    "elapsed_seconds": now - started_episode,
                    "scheduler_lag_seconds": now - next_tick,
                    "observation_before": before,
                    "action": action,
                    "action_source": source,
                    "decision_id": ready["id"] if ready is not None else None,
                    "pending_decision_id": (
                        decision["id"] if pending is not None else None
                    ),
                    "observation_after": copy.deepcopy(observation),
                    "score": float(score),
                    "score_change": float(score) - previous_score,
                    "collision": bool(collided),
                    "done": bool(done),
                })
                print(
                    f"Turn {env.game_turn:3d} | {action} | {source} | "
                    f"Score {score} | Collision {collided}",
                    flush=True,
                )
                ready = None

                # don't run a burst of catch-up turns after a scheduler delay
                # save any lag so we can assess the actual clock behavior
                next_tick = time.perf_counter() + args.tick_seconds
            else:
                # briefly yield CPU while keeping an eye on the next game tick
                time.sleep(min(0.01, next_tick - now))
    except BaseException as exception:
        error = f"{type(exception).__name__}: {exception}"
        raise
    finally:
        # save the episode even if a request is still running at its end
        # the game stops immediately; a late response cannot act on it

        # moving up from y=8 reaches the goal, including on turn 100
        last_step = episode["steps"][-1] if episode["steps"] else None
        reached_goal = bool(
            done and last_step and last_step["action"] == "U"
            and last_step["observation_before"]["state"]["player_states"] == 8
        )
        episode["summary"] = {
            "episode_ended": bool(done),
            "turns": int(env.game_turn),
            "collisions": collisions,
            "final_score": float(env.reward),
            "success": reached_goal,
            # Terminal observations are empty, so count the goal transition too.
            "maximum_position": max([9 if reached_goal else 0] + [
                int(step["observation_after"].get("state", {}).get("player_states", 0))
                for step in episode["steps"]]),
            "elapsed_seconds": time.perf_counter() - started_episode,
            "error": error,
        }

        def save_log():
            with log_path.open("w", encoding="utf-8") as file:
                json.dump(episode, file, indent=2, default=convert_scalar)

        if pending is not None:
            decision["status"] = "pending_when_episode_ended"
        save_log()
        print("\nEpisode log saved to:", log_path, flush=True)
        try:
            if pending is not None:
                # wait for the outstanding HTTP call so we can log its response
                # this wait is after the game has ended, not a paused game turn
                print(
                    "Waiting for the outstanding request; its action will be discarded.",
                    flush=True,
                )
                collect_response()
                decision["status"] = "discarded_after_episode"
            save_log()
        finally:
            worker.shutdown(wait=True)

    env.summary()


if __name__ == "__main__":
    main()
