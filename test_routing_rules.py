"""Offline behavior, validation and no-oracle checks for routing_rules.py.

Run: /usr/bin/python3.13 -m unittest test_routing_rules -v (also root discovery).
Inputs: synthetic scalars/configurations only; outputs: unittest assertions.
No simulator/model calls, seeds, outcomes or held-out records are consumed.
Related specification: docs/weekend/routing-rules.md; tests in this file.
"""

import inspect
import math
import unittest

import routing_rules as rules


# Synthetic fixtures exercise the interface, not an approved experiment config.
MODES = ("quick", "quick", "deliberate", "quick")
SPEED = dict(difficulty=2, world_speed=2, difficulty_threshold=5,
             world_speed_threshold=5, modes=MODES)
FRESH = dict(**SPEED, view_age_seconds=0, refresh_age_seconds=3)
DIFFICULTY = dict(difficulty=2, difficulty_threshold=5,
                  below="quick", at_or_above="deliberate")


class RoutingTests(unittest.TestCase):
    def test_fixed_rules(self):
        self.assertEqual(rules.always_quick(), "quick")
        self.assertEqual(rules.always_deliberate(), "deliberate")

    def test_difficulty_boundary_and_caller_direction(self):
        for difficulty, expected in ((0, "quick"), (4.999, "quick"),
                                     (5, "deliberate"), (6, "deliberate")):
            self.assertEqual(rules.difficulty_only(**dict(DIFFICULTY,
                             difficulty=difficulty)), expected)
        self.assertEqual(rules.difficulty_only(**dict(DIFFICULTY,
                         below="deliberate", at_or_above="quick")), "deliberate")

    def test_all_speed_regions_and_equalities(self):
        # Distinct table assignments in each pass detect wrong table indexing.
        for selected in range(4):
            modes = tuple("deliberate" if i == selected else "quick" for i in range(4))
            for difficulty in (0, 4.999, 5, 6):
                for speed in (0, 4.999, 5, 6):
                    expected = modes[2 * (difficulty >= 5) + (speed >= 5)]
                    config = dict(SPEED, difficulty=difficulty, world_speed=speed,
                                  modes=modes)
                    self.assertEqual(rules.world_speed(**config), expected)
                    self.assertEqual(rules.freshness_aware(**dict(config,
                                     view_age_seconds=0, refresh_age_seconds=3)), expected)

    def test_age_boundary_and_zero_threshold(self):
        for age, expected in ((0, "quick"), (2.999, "quick"),
                              (3, "refresh"), (4, "refresh")):
            self.assertEqual(rules.freshness_aware(**dict(FRESH,
                             view_age_seconds=age)), expected)
        self.assertEqual(rules.freshness_aware(**dict(FRESH,
                         refresh_age_seconds=0)), "refresh")
        self.assertEqual(rules.difficulty_only(**dict(DIFFICULTY,
                         difficulty=0, difficulty_threshold=0)), "deliberate")

    def test_five_documented_synthetic_situations(self):
        for difficulty, speed, age, expected in (
            (2, 2, 0, ("quick", "quick", "quick")),
            (6, 2, 0, ("deliberate", "deliberate", "deliberate")),
            (2, 6, 0, ("quick", "quick", "quick")),
            (6, 6, 0, ("deliberate", "quick", "quick")),
            (6, 2, 4, ("deliberate", "deliberate", "refresh")),
        ):
            with self.subTest(difficulty=difficulty, speed=speed, age=age):
                self.assertEqual(rules.always_quick(), "quick")
                self.assertEqual(rules.always_deliberate(), "deliberate")
                self.assertEqual((
                    rules.difficulty_only(**dict(DIFFICULTY, difficulty=difficulty)),
                    rules.world_speed(**dict(SPEED, difficulty=difficulty,
                                             world_speed=speed)),
                    rules.freshness_aware(**dict(FRESH, difficulty=difficulty,
                                                world_speed=speed, view_age_seconds=age)),
                ), expected)

    def test_invalid_scalars_for_every_numeric_input(self):
        for rule, config in ((rules.difficulty_only, DIFFICULTY),
                             (rules.world_speed, SPEED), (rules.freshness_aware, FRESH)):
            for key, value in config.items():
                if type(value) is not int:
                    continue
                for invalid in (-1, math.inf, -math.inf, math.nan, True,
                                None, "2", {}, object()):
                    with self.subTest(rule=rule.__name__, key=key, invalid=invalid):
                        with self.assertRaises((ValueError, TypeError)):
                            rule(**dict(config, **{key: invalid}))

    def test_missing_and_unsupported_inputs_fail(self):
        for rule, config in ((rules.always_quick, {}), (rules.always_deliberate, {}),
                             (rules.difficulty_only, DIFFICULTY),
                             (rules.world_speed, SPEED), (rules.freshness_aware, FRESH)):
            for key in config:
                missing = dict(config)
                del missing[key]
                with self.assertRaises(TypeError):
                    rule(**missing)
            # Explicit signatures reject labels without even inspecting values.
            for forbidden in ("future_outcome", "held_out_label", "reward",
                              "observation", "seed", "latency_seconds"):
                with self.assertRaises(TypeError):
                    rule(**dict(config, **{forbidden: OracleTrap()}))
        with self.assertRaises(TypeError):
            rules.world_speed(**dict(SPEED, view_age_seconds=0))
        with self.assertRaises(TypeError):
            rules.difficulty_only(**dict(DIFFICULTY, world_speed=1))

    def test_invalid_modes_even_when_refreshing(self):
        for invalid in (None, (), MODES + ("quick",), list(MODES),
                        ("quick", "quick", "deliberate", "refresh")):
            for rule, config in ((rules.world_speed, SPEED),
                                 (rules.freshness_aware, dict(FRESH, view_age_seconds=10))):
                with self.assertRaises(ValueError):
                    rule(**dict(config, modes=invalid))
        for key in ("below", "at_or_above"):
            with self.assertRaises(ValueError):
                rules.difficulty_only(**dict(DIFFICULTY, **{key: "refresh"}))

    def test_no_coercion_or_catch_all_or_mutation(self):
        for rule, config in ((rules.difficulty_only, DIFFICULTY),
                             (rules.world_speed, SPEED), (rules.freshness_aware, FRESH)):
            original = dict(config)
            self.assertEqual(rule(**config), rule(**config))
            self.assertEqual(config, original)
            with self.assertRaises(TypeError):
                rule(**dict(config, difficulty=OracleTrap()))
            self.assertFalse(any(p.kind == p.VAR_KEYWORD
                                 for p in inspect.signature(rule).parameters.values()))


# An oracle-like object explodes if coerced, compared, or queried. Rejecting it
# proves the boundary does not inspect a record to extract hidden labels.
class OracleTrap:
    def __float__(self):
        raise AssertionError("oracle coercion")

    def __ge__(self, other):
        raise AssertionError("oracle comparison")

    def __getattr__(self, name):
        raise AssertionError("oracle attribute access")


if __name__ == "__main__":
    unittest.main()
