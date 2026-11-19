"""Behavior/failure checks and bounded real-simulator snapshot demonstration.

Run: python -m unittest test_observation_history -v; no model calls or downloads.
Inputs: nested mutable fixtures and pinned seed-0 simulator actions. Outputs:
unittest assertions, including independent saved-smoke observation comparisons.
Tests observation_history.py; usage/runtime: docs/weekend/observation-history.md.
Simulator tests fail rather than skip if the provisioned runtime is unavailable.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from observation_history import ObservationHistory, demonstrate

ROOT = Path(__file__).resolve().parent


class HistoryTests(unittest.TestCase):
    def test_exact_age_and_independent_reads(self):
        history = ObservationHistory()
        observation = {"nested": [{"position": [1, 2]}]}
        history.append(4, observation)
        observation["nested"][0]["position"][0] = 99
        history.append(7, {"nested": [7]})
        older = history.retrieve(3)
        self.assertEqual(older, {"episode": 0, "current_turn": 7,
                               "source_turn": 4, "requested_delay": 3,
                               "actual_turn_age": 3, "terminal": False,
                               "current_terminal": False,
                               "observation": {"nested": [{"position": [1, 2]}]}})
        older["observation"]["nested"][0]["position"].append(9)
        older["source_turn"] = -1
        self.assertEqual(history.retrieve(3)["observation"],
                         {"nested": [{"position": [1, 2]}]})
        current = history.retrieve(0)
        current["observation"]["nested"].clear()
        self.assertEqual(history.retrieve(0)["observation"], {"nested": [7]})
        for delay in (1, 2, 4, 8):
            with self.subTest(delay=delay), self.assertRaises(LookupError):
                history.retrieve(delay)

    def test_invalid_delays_and_empty_history(self):
        history = ObservationHistory()
        with self.assertRaises(LookupError):
            history.retrieve(0)
        for delay in (-1, True, False, 1.0, "1", None):
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                history.retrieve(delay)
        history.append(0, {})
        with self.assertRaises(LookupError):
            history.retrieve(1)

    def test_bad_append_is_atomic(self):
        history = ObservationHistory()
        history.append(2, {"value": 2})
        for turn in (-1, True, 2.0, "3", None, 2, 1):
            with self.subTest(turn=turn), self.assertRaises(ValueError):
                history.append(turn, {"value": "bad"})
        for terminal in (0, 1, None, "false"):
            with self.subTest(terminal=terminal), self.assertRaises(ValueError):
                history.append(3, {}, terminal=terminal)
        class Uncopyable:
            def __deepcopy__(self, memo):
                raise TypeError("cannot copy")
        with self.assertRaises(TypeError):
            history.append(3, Uncopyable(), terminal=True)
        self.assertEqual(history.retrieve(0)["observation"], {"value": 2})
        history.append(3, {})
        self.assertEqual(history.retrieve(1)["source_turn"], 2)

    def test_terminal_and_episode_boundary(self):
        history = ObservationHistory()
        history.append(0, {"player": [1]})
        history.append(1, {}, terminal=True)
        terminal = history.retrieve(0)
        self.assertEqual(terminal["observation"], {})
        self.assertTrue(terminal["terminal"])
        self.assertTrue(terminal["current_terminal"])
        older = history.retrieve(1)
        self.assertFalse(older["terminal"])
        self.assertTrue(older["current_terminal"])
        with self.assertRaises(RuntimeError):
            history.append(2, {})
        history.reset()
        with self.assertRaises(LookupError):
            history.retrieve(0)
        history.append(0, {"new": True})
        self.assertEqual(history.retrieve(0)["episode"], 1)
        with self.assertRaises(LookupError):
            history.retrieve(1)
        self.assertEqual(older["observation"], {"player": [1]})
        history.reset()  # nonterminal episodes also require isolation
        history.append(0, {}, terminal=True)
        self.assertEqual(history.retrieve(0)["episode"], 2)
        self.assertTrue(history.retrieve(0)["terminal"])


# Compare to historical raw observations, not a second call to the history
# implementation alone, and exercise real terminal output through a bounded run.
class SimulatorTests(unittest.TestCase):
    def test_pairs_against_saved_observations(self):
        sample = [json.loads(line) for line in
                  (ROOT / "artifacts/freeway/smoke-seed0.jsonl").read_text().splitlines()]
        expected = [sample[1]["observation"],
                    *[record["after"] for record in sample[2:-1]]]
        for delay in (0, 2, 10):
            records = demonstrate(delay)
            pairs = records[1:-1]
            self.assertEqual(len(pairs), 11 - delay)
            self.assertEqual(records[0]["mapped_seed"], 1000)
            for turn, pair in enumerate(pairs, delay):
                self.assertEqual(pair["current"]["observation"], expected[turn])
                self.assertEqual(pair["older"]["observation"], expected[turn - delay])
                self.assertEqual(pair["older"]["actual_turn_age"], delay)
                self.assertEqual(pair["older"]["requested_delay"], delay)
                self.assertEqual(pair["older"]["source_turn"], turn - delay)
        self.assertEqual(demonstrate(2), demonstrate(2))
        with self.assertRaises(LookupError):
            demonstrate(11)
        with self.assertRaises(ValueError):
            demonstrate(-1)

    def test_real_terminal_is_empty_not_stale(self):
        records = demonstrate(1, actions="S" * 100, max_steps=100)
        final = records[-2]
        self.assertTrue(records[-1]["done"])
        self.assertEqual(records[-1]["step_count"], 100)
        self.assertEqual(final["current"]["observation"], {})
        self.assertTrue(final["current"]["terminal"])
        self.assertFalse(final["older"]["terminal"])
        self.assertEqual(final["older"]["source_turn"], 99)
        self.assertEqual(final["older"]["observation"]["game_turn"], 99)

    def test_cli_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pairs.jsonl"
            command = [sys.executable, str(ROOT / "observation_history.py"),
                       "--delay", "2", "--output", str(output)]
            env = os.environ.copy()
            env.pop("PYGAME_HIDE_SUPPORT_PROMPT", None)
            result = subprocess.run(command, check=True, capture_output=True, env=env,
                                    text=True, timeout=30)
            self.assertEqual(json.loads(result.stdout)["pairs"], 9)
            original = output.read_bytes()
            records = [json.loads(line) for line in original.splitlines()]
            self.assertEqual(records, demonstrate(2))
            retry = subprocess.run(command, capture_output=True, env=env, text=True, timeout=30)
            self.assertNotEqual(retry.returncode, 0)
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
