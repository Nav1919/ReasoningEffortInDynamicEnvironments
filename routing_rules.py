"""Pure offline routing proposals; no simulator, model, files, or clock access.

Usage: import always_quick, always_deliberate, difficulty_only, world_speed,
    freshness_aware. See docs/weekend/routing-rules.md for keyword-only examples.
Inputs: caller-supplied nonnegative finite scalar features, thresholds and modes.
Outputs: 'quick', 'deliberate', or (freshness only) 'refresh'; never a game action.
Validation: /usr/bin/python3.13 -m unittest test_routing_rules -v.
Tests: test_routing_rules.py; no scientific defaults or live-runner integration.
"""

import math


# Restrict features to plain numeric scalars: no observation/record objects or
# implicit coercion hooks can bring undeclared fields into the decision boundary.
def _scalar(name, value):
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be a plain int or float")
    if value < 0 or (type(value) is float and not math.isfinite(value)):
        raise ValueError(f"{name} must be finite and nonnegative")


def _mode(value):
    if type(value) is not str or value not in ("quick", "deliberate"):
        raise ValueError("mode must be 'quick' or 'deliberate'")


def _table(modes):
    if type(modes) is not tuple or len(modes) != 4:
        raise ValueError("modes must be a four-element tuple")
    for mode in modes:
        _mode(mode)


def always_quick():
    """Fixed policy with no decision-time inputs."""
    return "quick"


def always_deliberate():
    """Fixed policy with no decision-time inputs."""
    return "deliberate"


def difficulty_only(*, difficulty, difficulty_threshold, below, at_or_above):
    """Choose caller modes below/at-or-above the difficulty threshold."""
    _scalar("difficulty", difficulty)
    _scalar("difficulty_threshold", difficulty_threshold)
    _mode(below)
    _mode(at_or_above)
    return at_or_above if difficulty >= difficulty_threshold else below


# Both adaptive rules share exactly the same caller-defined 2x2 mode table.
# Index order is low/slow, low/fast, high/slow, high/fast, with equality high/fast.
def _speed_choice(*, difficulty, world_speed, difficulty_threshold,
                  world_speed_threshold, modes):
    for name, value in (("difficulty", difficulty), ("world_speed", world_speed),
                        ("difficulty_threshold", difficulty_threshold),
                        ("world_speed_threshold", world_speed_threshold)):
        _scalar(name, value)
    _table(modes)
    return modes[2 * (difficulty >= difficulty_threshold)
                 + (world_speed >= world_speed_threshold)]


def world_speed(*, difficulty, world_speed, difficulty_threshold,
                world_speed_threshold, modes):
    """Use only current difficulty and measured speed, never observation age."""
    return _speed_choice(
        difficulty=difficulty, world_speed=world_speed,
        difficulty_threshold=difficulty_threshold,
        world_speed_threshold=world_speed_threshold, modes=modes)


def freshness_aware(*, difficulty, world_speed, view_age_seconds,
                    difficulty_threshold, world_speed_threshold,
                    refresh_age_seconds, modes):
    """Request refresh at/above caller age threshold, otherwise use mode table.

    Validate every input even on refresh; malformed configuration never hides
    behind an early return. Refresh is a request only, with no I/O or retries.
    """
    _scalar("view_age_seconds", view_age_seconds)
    _scalar("refresh_age_seconds", refresh_age_seconds)
    mode = _speed_choice(
        difficulty=difficulty, world_speed=world_speed,
        difficulty_threshold=difficulty_threshold,
        world_speed_threshold=world_speed_threshold, modes=modes)
    return "refresh" if view_age_seconds >= refresh_age_seconds else mode
