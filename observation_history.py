"""Deep-copying, episode-local observation snapshots indexed by caller turns.

Import ObservationHistory; append(turn, observation, terminal=False), then
retrieve(delay) with an explicit integer delay. Returns a detached log record
containing observation, episode, source/current turns, requested/actual age and
terminal flags. No simulator dependency on import. CLI demonstration:
python observation_history.py --delay 2 --output NEW.jsonl
Inputs: bounded seed-0 simulator actions; output: metadata and current/older pairs.
Tests: python -m unittest test_observation_history -v; interface, manifest and
limits: docs/weekend/observation-history.md. No model calls.
"""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path


def _nonnegative_integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer (not bool)")


class ObservationHistory:
    """Retain one episode, with exact turn lookup and no padding or fallback.

    Turns may have gaps, but must strictly increase. The caller owns turn and
    episode semantics; observations are opaque deep-copyable Python values.
    Missing exact turns raise LookupError. Invalid inputs raise ValueError;
    append after terminal raises RuntimeError. No implicit reset or eviction.
    """

    def __init__(self):
        self._episode = -1
        self.reset()

    def reset(self):
        """Discard all snapshots and start a fresh local episode generation."""
        self._episode += 1
        self._snapshots = {}
        self._current_turn = None
        self._terminal = False

    # Copy before committing state so failed copies do not advance history.
    # Terminal is explicit because upstream may return an empty observation.
    def append(self, turn, observation, *, terminal=False):
        """Store a detached observation; even a terminal turn must increase."""
        _nonnegative_integer(turn, "turn")
        if type(terminal) is not bool:
            raise ValueError("terminal must be bool")
        if self._terminal:
            raise RuntimeError("episode ended; reset before appending")
        if self._current_turn is not None and turn <= self._current_turn:
            raise ValueError("turns must strictly increase")
        snapshot = deepcopy(observation)
        self._snapshots[turn] = (snapshot, terminal)
        self._current_turn = turn
        self._terminal = terminal

    # Use subtraction, not list offsets: omitted turns must never silently
    # change the requested age. Every retrieval is a fresh, loggable copy.
    def retrieve(self, delay):
        """Return a detached record for exactly current_turn - delay."""
        _nonnegative_integer(delay, "delay")
        if self._current_turn is None:
            raise LookupError("no observations in this episode")
        source_turn = self._current_turn - delay
        if source_turn not in self._snapshots:
            raise LookupError(f"turn {source_turn} unavailable in this episode")
        observation, terminal = self._snapshots[source_turn]
        return {"episode": self._episode, "current_turn": self._current_turn,
                "source_turn": source_turn, "requested_delay": delay,
                "actual_turn_age": self._current_turn - source_turn,
                "terminal": terminal, "current_terminal": self._terminal,
                "observation": deepcopy(observation)}


def demonstrate(delay, *, actions="USUSUSUSUS", max_steps=10):
    """Return bounded seed-0 current/older pairs, never a scientific condition.

    Reuse the source-verified smoke recorder rather than alter any live runner.
    Fail if the requested age is not reached; omit warm-up pairs explicitly.
    """
    _nonnegative_integer(delay, "delay")
    from scripts.freeway_smoke import run

    records = run(actions=actions, max_steps=max_steps)
    history = ObservationHistory()
    reset = records[1]
    history.append(0, reset["observation"], terminal=reset["done"])
    pairs = []
    for record in [reset, *records[2:-1]]:
        if record["type"] == "step":
            history.append(record["step"], record["after"], terminal=record["done"])
        current = history.retrieve(0)
        if current["current_turn"] >= delay:
            pairs.append({"type": "pair", "current": current,
                          "older": history.retrieve(delay)})
    if not pairs:
        raise LookupError("bounded run did not reach requested delay")
    metadata = dict(records[0], type="metadata", requested_delay=delay,
                    warmup_turns_omitted=delay, purpose="interface demonstration only")
    return [metadata, *pairs, records[-1]]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", required=True, type=int,
                        help="explicit demonstration age in turns, not a study choice")
    parser.add_argument("--actions", default="USUSUSUSUS")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    # Keep the simulator's Pygame startup banner out of the JSON response.
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    try:
        records = demonstrate(args.delay, actions=args.actions, max_steps=args.max_steps)
    except (ValueError, LookupError) as error:
        parser.error(str(error))
    # Exclusive creation preserves previous runs, including negative evidence.
    with args.output.open("x", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({"pairs": len(records) - 2, "summary": records[-1]}, sort_keys=True))


if __name__ == "__main__":
    main()
