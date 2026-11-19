# Offline routing interface proposal

Status: supporting code for human review, **not an approved/frozen scientific
policy**, live controller, or performance result. No runner imports these rules.
The project outline, model, experiment settings and evaluation protocol are unchanged.

## Task contract

- **Hypothesis:** configurable routing can be implemented and independently
  checked offline without choosing scientific thresholds or using oracle labels.
- **Dependencies:** baseline `22cdee9`; standard-library-only
  [routing_rules.py](../../routing_rules.py) and
  [test_routing_rules.py](../../test_routing_rules.py). Full regression checks use
  provisioned Python 3.13 and RealtimeGym
  `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b`.
- **Acceptance:** fixed/adaptive decisions, exact boundaries, invalid/missing
  parameters, declared-input isolation, and both repository test discoveries.
- **Artifacts:** those two code files, this specification and README navigation;
  actual check results and commit SHA accompany the board review handoff.
- **Seed/config manifest:** no RNG or seeds. All numeric values below are
  synthetic test fixtures, not approved experimental parameters. No frozen model
  is loaded or modified. Callers must separately record approved feature units,
  derivations, thresholds and modes before any research use.
- **Compute allowance:** local offline unit/simulator regression tests only;
  no installs, network, inference or paid experiments. Coding-assistant
  subscription authorized; metered subscription usage is unavailable here.
- **Stop condition:** passing tested local commit and human-review request;
  no publishing, live integration, tuning or held-out evaluation.

## Interface and declared inputs

All adaptive arguments are required and keyword-only. Outputs are plain strings
`quick`, `deliberate`, or `refresh`, not Freeway U/D/S actions or model settings.

| Function | Decision-time inputs | Required caller configuration |
|---|---|---|
| `always_quick()` | none | none |
| `always_deliberate()` | none | none |
| `difficulty_only(...)` | `difficulty` | `difficulty_threshold`, `below`, `at_or_above` |
| `world_speed(...)` | `difficulty`, `world_speed` | `difficulty_threshold`, `world_speed_threshold`, `modes` |
| `freshness_aware(...)` | `difficulty`, `world_speed`, `view_age_seconds` | same as world-speed plus `refresh_age_seconds` |

Difficulty and speed must be caller-derived nonnegative finite plain `int`/`float`
scalars in caller-documented units. These functions do not infer difficulty from
traffic or equate tick duration with world speed. Speed must represent the chosen
measured quantity; a larger value selects the high-speed table column. The
caller is responsible for validating its relationship to actual traffic change.
Age and its threshold are in seconds in the same caller-defined time basis;
there is no clock read. Booleans, strings, objects, negatives, NaN and infinities
are rejected. Zero is accepted, including zero thresholds.

Difficulty-only selects `below` when difficulty is strictly below threshold,
otherwise `at_or_above`. Both are caller-supplied `quick`/`deliberate` strings;
the implementation assumes no preferred direction.

`modes` is an exact four-element tuple of `quick`/`deliberate` strings in this
order: **low difficulty/low speed, low/high, high/low, high/high**. Equality to a
threshold belongs to the high side. Repeated modes are allowed. The complete
caller table avoids embedding a scientific assumption about either feature.

Freshness first validates all fields/configuration. At age **greater than or
equal to** `refresh_age_seconds`, it returns `refresh`; otherwise it uses the
same 2×2 mode table. This precedence and rectangular interface are proposals for
review, not a fitted or approved rule. Refresh requests only a new view; it does
not acquire one, choose a subsequent action, reset age, account for refresh cost,
or loop. A future caller must measure refresh time/cost and decide when/if to
call again; repeated stale inputs can repeatedly return `refresh`.

Missing arguments and extra/unsupported keywords raise `TypeError`; invalid
scalar types raise `TypeError`; invalid values or mode tables raise `ValueError`.
There is no silent fallback, threshold default, tuning, or automatic refresh.

## Five common synthetic situations

For illustration only: difficulty threshold **5**, speed threshold **5**,
refresh threshold **3 seconds**, difficulty modes `quick` below / `deliberate`
at-or-above, and `modes=('quick', 'quick', 'deliberate', 'quick')`.
These arbitrary numbers and choices demonstrate branches, **not performance
evidence or recommended scientific settings**.

| Situation | Difficulty | Speed | Age (s) | Always quick | Always deliberate | Difficulty only | World speed | Freshness aware |
|---|---:|---:|---:|---|---|---|---|---|
| Easy, slow, fresh | 2 | 2 | 0 | quick | deliberate | quick | quick | quick |
| Hard, slow, fresh | 6 | 2 | 0 | quick | deliberate | deliberate | deliberate | deliberate |
| Easy, fast, fresh | 2 | 6 | 0 | quick | deliberate | quick | quick | quick |
| Hard, fast, fresh | 6 | 6 | 0 | quick | deliberate | deliberate | quick | quick |
| Hard, slow, stale | 6 | 2 | 4 | quick | deliberate | deliberate | deliberate | refresh |

Conditional hypotheses for later approved tests: this example table predicts
longer reasoning is worth considering on hard/slow states, that difficulty-only
could waste compute on hard/fast states, and that refreshing stale views could
help only if its information benefit exceeds its time/cost. None is established
by these examples or the software tests.

```python
from routing_rules import freshness_aware

choice = freshness_aware(
    difficulty=6, world_speed=2, view_age_seconds=4,
    difficulty_threshold=5, world_speed_threshold=5,
    refresh_age_seconds=3,
    modes=("quick", "quick", "deliberate", "quick"),
)
assert choice == "refresh"
```

## Input isolation and verification

The narrow function signatures accept no episode record, observation object,
held-out label, seed, future outcome, action-time state or measured future
latency. No I/O, global experiment configuration, simulator, model or clock is
consulted. Tests reject extra oracle fields and objects with access/coercion
traps, check all table regions and boundaries, and check repeated-call and
non-mutation behavior. They cannot prove an upstream caller computed its scalar
features without leakage: feature provenance and held-out separation still need
human review before integration. No thresholds may be tuned on held-out starts.

From repository root, for the routing-only checks:

```sh
/usr/bin/python3.13 -m unittest test_routing_rules -v
```

For each full regression command, use this environment (no installation needed):

```sh
export PYTHONPATH=/opt/data/research/freeway/source/src:/opt/data/research/freeway/site-packages
export SDL_VIDEODRIVER=dummy
export PYGAME_HIDE_SUPPORT_PROMPT=1
/usr/bin/python3.13 -m unittest discover -v
/usr/bin/python3.13 -m unittest discover -s tests -v
```

Tests are correctness/isolation evidence only, not routing efficacy. Live/model
runs, held-out comparisons, refresh economics and scientific threshold selection
are deliberately not performed. GitHub publishing is a separate host step after
human review; this milestone is local only. Hermes/Codex assisted implementation
and tests; the human author identity is distinct from authentication and signing.

### Local verification — October 30, 2026

Using `/usr/bin/python3.13` (3.13.5) and the environment above:

| Actual command | Result |
|---|---|
| `/usr/bin/python3.13 -m unittest discover -v` | PASS: 23 tests, including 9 routing tests, 4.523 s |
| `/usr/bin/python3.13 -m unittest discover -s tests -v` | PASS: 7 tests, 0.896 s |
| `git diff --check` | PASS: no whitespace errors |

The initial routing-only run passed 8 tests before the documented-situations
regression was added; the final root discovery passed all 9 routing tests.
No failed test runs occurred. No model calls or experimental game comparisons
were run. Commit identity was checked against repository configuration and the
baseline commit: Pranav Panicker <75394407+Nav1919@users.noreply.github.com>.
Agent assistance is disclosed in the commit message; no authentication or
signing settings were changed.
