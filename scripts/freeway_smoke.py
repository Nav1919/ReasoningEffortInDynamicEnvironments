"""Bounded no-LLM Freeway recorder; run with --help for CLI inputs/outputs.

Imports upstream via PYTHONPATH, never downloads dependencies. JSONL contains
metadata, raw reset/step observations and a final summary. Tested by
`python -m unittest discover -s tests -v`; see docs/freeway-setup.md.
"""

import argparse
import copy
import hashlib
import json
import platform
from pathlib import Path

REVISION = "3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b"
DIFFICULTIES = {"Freeway-v0": "E", "Freeway-v1": "M", "Freeway-v2": "H"}
DEFAULT_ACTIONS = "USUSUSUSUS"
# Verify the imported selected-source path, not an unrelated checkout's Git HEAD.
SOURCE_HASHES = {
    "__init__.py": "1c6c6638129b196ea20fb63b41666e3b16c03833e9df37131d6177670caac6ed",
    "environments/base.py": "139b45e947c99bf9d4b929712167590d28338f8405e2669bfe4fa4b46628650a",
    "environments/freeway.py": "9a0a252cb1db44830920268f745f0dadd3a00e4ccbe6863b36a38daa3126367a",
    "environments/render/freeway_render.py": "a7bc924fbf14d9631af2735d3a38088922953786e45274e88208373153978430",
}


def validate_settings(environment, difficulty, seed, actions, max_steps):
    """Reject unsupported settings before constructing an environment."""
    if environment not in DIFFICULTIES:
        raise ValueError("environment must be Freeway-v0, Freeway-v1 or Freeway-v2")
    if difficulty != DIFFICULTIES[environment]:
        raise ValueError("difficulty must match environment: v0=E, v1=M, v2=H")
    if type(seed) is not int or not 0 <= seed <= 7:
        raise ValueError("input seed must be an integer in 0..7")
    if not actions or any(action not in "UDS" for action in actions):
        raise ValueError("actions must be a nonempty sequence of U/D/S")
    if type(max_steps) is not int or not 1 <= max_steps <= 100:
        raise ValueError("max_steps must be an integer in 1..100")


def run(environment="Freeway-v0", difficulty="E", seed=0,
        actions=DEFAULT_ACTIONS, max_steps=10):
    """Return JSON-compatible records; stop on done, action exhaustion or limit."""
    validate_settings(environment, difficulty, seed, actions, max_steps)
    import realtimegym
    import numpy
    import pygame
    from realtimegym.environments.freeway import seed_mapping

    root = Path(realtimegym.__file__).resolve().parent
    for relative, expected in SOURCE_HASHES.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"pinned source hash mismatch: {relative}")
    env, mapped_seed, _ = realtimegym.make(environment, seed=seed, render=False)
    if mapped_seed != seed_mapping[difficulty][seed] or env.seed != mapped_seed:
        raise ValueError("mapped seed mismatch")
    records = [{"type": "metadata", "schema_version": 1,
                "source_revision": REVISION, "source_sha256": SOURCE_HASHES,
                "versions": {"python": platform.python_version(),
                             "realtimegym": realtimegym.__version__,
                             "numpy": numpy.__version__, "pygame": pygame.version.ver},
                "environment": environment, "difficulty": difficulty,
                "input_seed": seed, "mapped_seed": mapped_seed,
                "actions": actions, "max_steps": max_steps,
                "render": False, "upstream_turn_limit": 100}]
    observation, done = env.reset()
    records.append({"type": "reset", "observation": copy.deepcopy(observation), "done": done})
    reward = env.reward
    count = 0
    # Snapshot before step: an environment may mutate objects in its observations.
    for action in actions[:max_steps]:
        if done:
            break
        before = copy.deepcopy(observation)
        observation, done, reward, collision_reset = env.step(action)
        count += 1
        records.append({"type": "step", "step": count, "action": action,
                        "before": before, "after": copy.deepcopy(observation),
                        "done": done, "reward": reward, "reset": collision_reset})
    records.append({"type": "summary", "step_count": count,
                    "final_cumulative_reward": reward, "done": done,
                    "stop_reason": "done" if done else
                    "max_steps" if count == max_steps else "actions_exhausted"})
    # JSON roundtrip preserves all observation values while converting upstream
    # tuples to JSON arrays. No wall-clock values enter deterministic records.
    return json.loads(json.dumps(records, allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", default="Freeway-v0")
    parser.add_argument("--difficulty", default="E", help="E/M/H; must match environment")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--actions", default=DEFAULT_ACTIONS, help="finite U/D/S string; never cycled")
    parser.add_argument("--max-steps", type=int, default=10)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        records = run(args.environment, args.difficulty, args.seed, args.actions, args.max_steps)
    except ValueError as error:
        parser.error(str(error))
    # Refuse overwrite so prior or negative evidence cannot silently disappear.
    with args.output.open("x", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(records[-1], sort_keys=True))


if __name__ == "__main__":
    main()
