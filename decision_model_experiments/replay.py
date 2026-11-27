"""Verify and inspect saved decision-model Freeway episodes without inference.

Run from the repository root with the existing Freeway dependencies:
    python -m decision_model_experiments.replay logs/both_test.json
    python -m decision_model_experiments.replay EPISODE.json --verify-only

Inputs: the runner's JSON (or gzip JSON), including partial/failed episodes.
Output: a read-only pygame debugger, or a JSON verification report. No Ollama
calls, log edits, new sampling, or reconstruction of missing model text occur.
Simulator snapshots retain raw car positions/timers for the same GUI used live.
Tests: python -m unittest discover -s tests -p 'test_decision_replay.py' -v
See decision_model_experiments/replay.md for controls and verification limits.
"""

import argparse
import copy
from dataclasses import dataclass
import gzip
import json
from pathlib import Path

from decision_model_experiments.experiment_runner import convert_scalar, _make_freeway


@dataclass(frozen=True)
class ReplayState:
    """A detached simulator snapshot accepted by draw_freeway_surface."""

    pos: int
    cars: list
    game_turn: int
    reward: float
    terminal: bool

    @classmethod
    def capture(cls, env):
        return cls(int(env.pos), copy.deepcopy(env.cars), int(env.game_turn),
                   float(env.reward), bool(env.terminal))


def plain(value):
    return json.loads(json.dumps(value, default=convert_scalar))


def pretty(value):
    return json.dumps(value, indent=2, ensure_ascii=False, default=convert_scalar)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass
class ReplayTrace:
    """Saved evidence and verified states; index i brackets action i with i+1."""

    episode: dict
    states: list

    @classmethod
    def verify(cls, episode):
        # Refuse another runner's schema rather than guessing how prompts or
        # observer IDs should be interpreted. Failure-only logs remain readable.
        _require(isinstance(episode, dict), "Episode must be a JSON object")
        _require(episode.get("environment") == "Freeway-v0", "Expected Freeway-v0")
        _require(isinstance(episode.get("settings"), dict), "Missing settings")
        _require(episode["settings"].get("context_mode") in
                 ("observation", "reasoning", "both"), "Missing decision-model context_mode")
        for key in ("steps", "observer_cycles"):
            _require(isinstance(episode.get(key), list), f"Missing {key} list")
        _require(isinstance(episode.get("summary"), dict), "Missing summary")
        initial = episode.get("initial_observation")
        if initial is None:
            _require(not episode["steps"] and bool(episode["summary"].get("error")),
                     "Missing initial observation without a recorded setup failure")
            return cls(episode, [])

        env, real_seed, _ = _make_freeway(episode["requested_seed"])
        observation, done = env.reset()
        _require(int(real_seed) == episode.get("real_seed"),
                 "Starting seed differs; check the simulator revision")
        _require(plain(observation) == initial,
                 "Starting state differs; check the simulator revision")
        states = [ReplayState.capture(env)]
        collisions = 0
        cycles = {cycle["id"]: cycle for cycle in episode["observer_cycles"]}
        _require(len(cycles) == len(episode["observer_cycles"]), "Duplicate observer cycle ID")
        for index, step in enumerate(episode["steps"], 1):
            _require(not done, f"Saved actions continue after termination at step {index}")
            _require(step["action"] in ("U", "D", "S"), f"Invalid action at step {index}")
            _require(plain(observation) == step["observation_before"],
                     f"Observation mismatch before step {index}")
            cycle_id = step.get("observer_cycle_id")
            _require(cycle_id is None or cycle_id in cycles,
                     f"Unknown observer cycle at step {index}")
            observation, done, score, collision = env.step(step["action"])
            actual = (plain(observation), bool(done), float(score), bool(collision),
                      int(env.game_turn))
            expected = (step["observation_after"], step["done"], step["score"],
                        step["collision"], step["turn"])
            _require(actual == expected, f"Transition mismatch at step {index}")
            collisions += int(collision)
            states.append(ReplayState.capture(env))
        summary = episode["summary"]
        last = episode["steps"][-1] if episode["steps"] else {}
        success = bool(done and last.get("action") == "U" and
                       last["observation_before"]["state"]["player_states"] == 8)
        _require((summary.get("turns"), summary.get("collisions"),
                  summary.get("final_score"), summary.get("episode_ended"),
                  summary.get("success")) ==
                 (int(env.game_turn), collisions, float(env.reward), bool(done), success),
                 "Summary differs from replayed actions")
        return cls(episode, states)

    def report(self):
        return {
            "verification": "transitions verified" if self.states else "no game state recorded",
            "verified_steps": len(self.episode["steps"]),
            "collisions": sum(int(s["collision"]) for s in self.episode["steps"]),
            "episode_error": self.episode["summary"].get("error"),
        }

    def step(self, index):
        return self.episode["steps"][index] if self.episode["steps"] else None

    def cycle(self, index):
        step = self.step(index)
        if step is None:
            # Empty observer failures have no actor step; expose the last call.
            return next(iter(self.episode["observer_cycles"][-1:]), None)
        return next((c for c in self.episode["observer_cycles"]
                     if c["id"] == step.get("observer_cycle_id")), None)

    def state(self, index, after=False):
        if not self.states:
            return None
        return self.states[index + int(after)] if self.episode["steps"] else self.states[0]

    def panels(self, index):
        """Readable views of saved text. Never regenerate a prompt from new code."""
        step = self.step(index) or {}
        cycle = self.cycle(index) or {}
        actor = step.get("actor_result") or {}
        observer = cycle.get("generation") or {}
        count = step.get("revealed_token_count", 0)
        trace = cycle.get("reasoning", "")
        # The runner uses whitespace joins for its reveal approximation. If a
        # future tokenizer changes, show the recorded context and avoid guessing.
        method = cycle.get("tokenization_method",
                           self.episode["settings"].get("tokenization_method"))
        if method == "whitespace":
            prefix = " ".join(trace.split()[:count])
            remaining = " ".join(trace.split()[count:])
        else:
            prefix = "Unavailable: unknown tokenizer. See exact actor context below."
            remaining = "Unavailable: unknown tokenizer. Full saved trace below."
        missing = "Not recorded."
        no_cycle = "No observer call for this step (observation mode)."
        sections = {
            "Actor prompt": [
                ("Exact saved actor prompt", actor.get("prompt", missing)),
                ("Exact saved actor context", step.get("context", missing)),
            ],
            "Reasoning": [
                (f"Revealed to actor: {count} tokens ({method})", prefix if cycle else no_cycle),
                ("Not yet revealed to actor", remaining if cycle else no_cycle),
                ("Full saved observer trace (debugger only)", trace if cycle else no_cycle),
            ],
            "Observer prompt": [
                ("Exact saved observer prompt", observer.get("prompt", missing) if cycle else no_cycle),
                ("Observer's original observation (may be stale)",
                 pretty(cycle.get("observation")) if cycle else no_cycle),
            ],
            "Outputs": [
                ("Actor output", actor.get("content", missing)),
                ("Actor recorded thinking", actor.get("thinking", missing)),
                ("Actor error / termination / usage", pretty({key: actor.get(key)
                 for key in ("error", "done_reason", "input_tokens", "output_tokens", "latency_seconds")})),
                ("Observer error / termination / usage", pretty({key: observer.get(key)
                 for key in ("error", "done_reason", "input_tokens", "output_tokens", "latency_seconds")})),
                ("Complete saved actor generation", pretty(step.get("actor_result"))),
                ("Complete saved observer generation", pretty(cycle.get("generation"))),
            ],
            "State": [
                ("Before action", pretty(step.get("observation_before", self.episode.get("initial_observation")))),
                ("After action", pretty(step.get("observation_after"))),
                ("Observer snapshot", pretty(cycle.get("observation"))),
            ],
            "Episode": [
                ("Verification (game transitions only)", pretty(self.report())),
                ("Settings / seed manifest", pretty({key: self.episode.get(key) for key in
                 ("environment", "requested_seed", "real_seed", "settings")})),
                ("Summary (includes recorded failures)", pretty(self.episode["summary"])),
                ("All observer calls (includes calls without actions)", pretty(self.episode["observer_cycles"])),
                ("Model metadata", pretty(self.episode.get("model_metadata"))),
                ("Warmup", pretty(self.episode.get("warmup"))),
            ],
        }
        return {name: "\n\n".join(f"{title.upper()}\n{value if value is not None else missing}"
                                 for title, value in values)
                for name, values in sections.items()}


def load_trace(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as source:
        return ReplayTrace.verify(json.load(source))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode", type=Path)
    parser.add_argument("--verify-only", action="store_true", help="Verify without opening a window")
    args = parser.parse_args(argv)
    try:
        trace = load_trace(args.episode)
    except (OSError, ValueError, KeyError, TypeError) as exception:
        parser.exit(1, f"Replay failed: {exception}\n")
    print(pretty(trace.report()))
    if not args.verify_only:
        from decision_model_experiments.replay_gui import ReplayWindow
        ReplayWindow(trace, args.episode.name).run()
    return trace.report()


if __name__ == "__main__":
    main()
