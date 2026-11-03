"""Validate runner settings, tuple semantics and real Freeway repeatability.

Run: python -m unittest discover -s tests -v (pinned runtime on PYTHONPATH).
Integration runs one independent ten-step CLI process against the saved actual
sample. It fails, rather than skips, when runtime/sample is missing. No LLM.
"""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("freeway_smoke", ROOT / "scripts/freeway_smoke.py")
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def check_sample(test, records):
    """Independent expected values detect seed/action/record regressions."""
    metadata, reset, *tail = records
    steps, summary = tail[:-1], tail[-1]
    test.assertEqual(len(records), 13)
    test.assertEqual(metadata["type"], "metadata")
    test.assertEqual(metadata["source_revision"], smoke.REVISION)
    test.assertEqual(metadata["environment"], "Freeway-v0")
    test.assertEqual(metadata["difficulty"], "E")
    test.assertEqual(metadata["input_seed"], 0)
    test.assertEqual(metadata["mapped_seed"], 1000)
    test.assertEqual(metadata["actions"], "USUSUSUSUS")
    test.assertEqual(metadata["max_steps"], 10)
    test.assertEqual(reset["type"], "reset")
    test.assertFalse(reset["done"])
    test.assertEqual(reset["observation"]["game_turn"], 0)
    previous = reset["observation"]
    for index, (step, action) in enumerate(zip(steps, "USUSUSUSUS"), 1):
        test.assertEqual(step["type"], "step")
        test.assertEqual(step["step"], index)
        test.assertEqual(step["action"], action)
        test.assertEqual(step["before"], previous)
        test.assertEqual(step["after"]["game_turn"], index)
        test.assertEqual(step["reward"], 100 - index)
        test.assertIs(type(step["done"]), bool)
        test.assertIs(type(step["reset"]), bool)
        test.assertFalse(step["done"])
        previous = step["after"]
    test.assertEqual(summary, {"type": "summary", "step_count": 10,
                              "final_cumulative_reward": 90, "done": False,
                              "stop_reason": "max_steps"})


class SettingsTests(unittest.TestCase):
    def test_supported_settings(self):
        for environment, difficulty in smoke.DIFFICULTIES.items():
            for seed in range(8):
                smoke.validate_settings(environment, difficulty, seed, "UDS", 100)

    def test_invalid_settings(self):
        for change in ({"environment": "Snake-v0"}, {"difficulty": "H"},
                       {"seed": -1}, {"seed": 8}, {"seed": True},
                       {"actions": ""}, {"actions": "UX"}, {"actions": "u"},
                       {"max_steps": 0}, {"max_steps": 101}):
            settings = dict(environment="Freeway-v0", difficulty="E", seed=0,
                            actions="UDS", max_steps=10)
            settings.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                smoke.validate_settings(**settings)

    def test_tuple_order_collision_and_terminal(self):
        class FakeEnv:
            seed = 1000
            reward = 100
            calls = 0
            observation = {"game_turn": 0, "nested": [0]}

            def reset(self):
                return self.observation, False

            def step(self, action):
                self.calls += 1
                self.observation["nested"][0] = self.calls
                if self.calls == 1:
                    return self.observation, False, 99, True
                return {}, True, 98, False

        env = FakeEnv()
        with patch("realtimegym.make", return_value=(env, 1000, None)):
            records = smoke.run(actions="UDS")
        self.assertEqual(env.calls, 2)  # collision is not terminal
        self.assertEqual(records[1]["observation"]["nested"], [0])
        self.assertEqual(records[2]["before"]["nested"], [0])
        self.assertTrue(records[2]["reset"])
        self.assertFalse(records[2]["done"])
        self.assertEqual(records[3]["after"], {})
        self.assertEqual(records[-1]["final_cumulative_reward"], 98)  # not 197
        self.assertEqual(records[-1]["stop_reason"], "done")

    def test_bad_mapped_seed_rejected(self):
        with patch("realtimegym.make", return_value=(object(), 999, None)):
            with self.assertRaisesRegex(ValueError, "mapped seed"):
                smoke.run()

    def test_source_mismatch_rejected(self):
        with patch.object(smoke, "SOURCE_HASHES", {"__init__.py": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "source hash"):
                smoke.run()

    def test_action_exhaustion(self):
        class FakeEnv:
            seed = 1000
            reward = 100
            def reset(self):
                return {}, False
            def step(self, action):
                return {}, False, 99, False
        with patch("realtimegym.make", return_value=(FakeEnv(), 1000, None)):
            records = smoke.run(actions="D")
        self.assertEqual(records[2]["action"], "D")
        self.assertEqual(records[-1]["step_count"], 1)
        self.assertEqual(records[-1]["stop_reason"], "actions_exhausted")


class RealEnvironmentTests(unittest.TestCase):
    def test_independent_cli_repeatability_and_record_oracles(self):
        sample = [json.loads(line) for line in
                  (ROOT / "artifacts/freeway/smoke-seed0.jsonl").read_text().splitlines()]
        check_sample(self, sample)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "repeat.jsonl"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/freeway_smoke.py"),
                                     "--output", str(output)],
                                    env=os.environ.copy(), text=True, capture_output=True,
                                    timeout=30, check=True)
            repeated = [json.loads(line) for line in output.read_text().splitlines()]
        check_sample(self, repeated)
        self.assertEqual(sample, repeated)  # all raw observations and provenance
        self.assertEqual(json.loads(result.stdout)["step_count"], 10)
        for index, key, value in ((0, "input_seed", 1), (0, "mapped_seed", 1001),
                                  (2, "action", "D"), (2, "reward", 0),
                                  (2, "before", {}), (2, "step", 2)):
            corrupted = copy.deepcopy(sample)
            corrupted[index][key] = value
            with self.subTest(key=key), self.assertRaises(AssertionError):
                check_sample(self, corrupted)


if __name__ == "__main__":
    unittest.main()
