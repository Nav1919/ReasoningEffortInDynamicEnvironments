# Current and delayed observation snapshots (review proposal)

## Scope and research contract

**Hypothesis:** episode-local deep copies with exact turn lookup can supply
verifiable current/older pairs offline without changing approved scientific choices.
This is a supporting interface, not an adopted experiment condition or evidence
that older observations affect model quality. No live runner is modified.

**Dependencies:** baseline `22cdee9`; Python standard library for the history;
for demonstration/integration tests, provisioned RealtimeGym revision
`3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b` and the existing
[source-verified smoke recorder](../../scripts/freeway_smoke.py).
No installation, network, model calls or paid experiments are required.

**Compute allowance / stop:** local offline tests and bounded scripted actions
only; at most 100 simulator steps per demonstration, never wall-clock sleeps.
Stop at a tested human-review milestone within the card's 1200-second allowance.
Coding-assistant subscription use is authorized; token/currency usage is not
exposed to this worker. No additional compute purchases were made.

**Acceptance:** exact requested age, deep-copy mutation isolation, explicit
failure for invalid/unavailable requests, monotonic turns, episode isolation,
terminal handling, deterministic simulator pairs and both existing discovery
suites passing. [Tests](../../test_observation_history.py) exercise these checks.

## Proposed API

```python
from observation_history import ObservationHistory

history = ObservationHistory()  # local episode generation 0, initially empty
history.append(0, {"player": [0]})
history.append(1, {"player": [1]})
current = history.retrieve(0)
older = history.retrieve(1)  # caller explicitly supplies the age
history.append(2, {}, terminal=True)
terminal = history.retrieve(0)  # preserves {}, never substitutes an older state
history.reset()  # generation 1; all prior snapshots unavailable
```

The history is simulator-independent. Callers supply nonnegative integer turns,
strictly increasing within each episode (bools and floats are rejected). Gaps are
permitted, but `retrieve(delay)` requires exactly `latest_turn - delay`; it raises
`LookupError` for empty history, gaps, pre-episode turns or insufficient history.
There is no rounding, clipping, nearest snapshot, warm-up padding or default delay.
Invalid delay/turn/terminal arguments raise `ValueError`. Copies that fail propagate
their original exception without committing append state.

Append deep-copies the input, and each retrieval deep-copies stored observations.
Mutating an input, one result or a result's metadata cannot alter another result.
Observations are opaque deep-copyable values; the library does not infer turns
from their contents or validate simulator-specific observation schemas. Callers
must pass the authoritative turn (e.g. `env.game_turn` on an empty terminal result).
No threading or concurrent access guarantee is proposed. All snapshots remain in
memory until explicit reset; there is no automatic eviction or persistence.

`retrieve` returns the following loggable dictionary. The library itself does not
write logs; the demo writes these records as JSONL. Arbitrary library observations
need not be JSON-serializable.

| Field | Meaning |
|---|---|
| `episode` | Instance-local generation, incremented by reset; not a global run ID |
| `current_turn` | Latest appended turn in this episode |
| `source_turn` | Exact retrieved turn |
| `requested_delay` | Caller-specified age in turns |
| `actual_turn_age` | `current_turn - source_turn`, equal to requested age on success |
| `terminal` | Whether the retrieved source snapshot ends the episode |
| `current_terminal` | Whether the latest snapshot ends the episode |
| `observation` | Detached full source observation |

After terminal append, older and terminal snapshots remain available for audit,
but append raises `RuntimeError` until reset. Empty terminal observations are not
usable decision views. A collision is **not** an episode boundary; do not call
history reset for the simulator's collision-reset flag. Reset must accompany an
actual new episode even when the prior episode was nonterminal. Previously returned
records remain detached after reset. Age is simulator turns, not seconds, inference
latency or a measure of consequential state change.

## Reproduce a bounded demonstration

From the repository root in the provisioned runtime:

```sh
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/opt/data/research/freeway/source/src:/opt/data/research/freeway/site-packages
export SDL_VIDEODRIVER=dummy
export PYGAME_HIDE_SUPPORT_PROMPT=1
/usr/bin/python3.13 observation_history.py --delay 2 --output NEW-pairs.jsonl
/usr/bin/python3.13 -m unittest test_observation_history -v
/usr/bin/python3.13 -m unittest discover -v
/usr/bin/python3.13 -m unittest discover -s tests -v
```

**Seed/config manifest:** Freeway-v0/E, input seed 0 → mapped seed 1000,
`render=False`, synchronous fixed actions `USUSUSUSUS`, max 10 steps, no model.
Delay **2 is a demonstration input only**, not the scientific older-view choice.
CLI requires `--delay`; optional `--actions` and `--max-steps` obey the existing
smoke bounds (UDS only, 1–100 steps). Output is exclusively created, never overwritten.
A delay not reached by the bounded run fails rather than emitting a successful
empty comparison. Warm-up turns are omitted and their count is in metadata.
Metadata includes source hashes and actual runtime versions. Output contains one
metadata record, current/older pairs and the unchanged simulator summary.

## Actual validation, October 30, 2026

Runtime: Python 3.13.5, NumPy 2.2.6, pygame 2.6.1, RealtimeGym 0.1.0;
selected source hashes verified by the existing recorder on every demo run.
All commands below used the four environment settings above.

| Command | Actual result |
|---|---|
| `/usr/bin/python3.13 -m unittest test_observation_history -v` | 7 tests passed |
| `/usr/bin/python3.13 -m unittest discover -v` | 21 tests passed, including saved pilot replay/integrity checks |
| `/usr/bin/python3.13 -m unittest discover -s tests -v` | 7 tests passed |
| `/usr/bin/python3.13 observation_history.py --delay 2 --output /opt/data/profiles/coder/cache/scratch/t_a190f857/pairs-delay2.jsonl` | 9 pairs, 10 steps, cumulative reward 90, done false, max_steps stop |

The generated JSONL is a local disposable artifact at the path above, not a new
historical evidence claim. It can be regenerated with the documented command and
a fresh output filename. Full observations are checked against the unchanged
historical `artifacts/freeway/smoke-seed0.jsonl`, not only against another call to
the new implementation. Delays 0, 2 and 10 are checked; 11 fails for this 10-step
run. Repeated records are identical. CLI execution and overwrite rejection pass.
A separate `S` × 100 test reaches the actual upstream timeout: the current view is
terminal `{}` at turn 100 while the older view is nonterminal turn 99.

Two excerpts from the actual delay-2 output (player is `state.player_states`):

| Latest turn | Current source / age / player | Older source / requested / actual age / player |
|---|---|---|
| 2 | 2 / 0 / 1 | 0 / 2 / 2 / 0 |
| 10 | 10 / 0 / 1 | 8 / 2 / 2 / 0 |

**Preserved failure:** initial `/usr/bin/python3.13 -m py_compile
observation_history.py test_observation_history.py` exited 1 with
`[Errno 30] Read-only file system: '/opt/data/.cache'` due to the runtime's bytecode
cache configuration. No infrastructure was changed. All subsequent execution used
`PYTHONDONTWRITEBYTECODE=1`; successful imports/tests exercised both files.
No model inference, live-runner integration, held-out evaluation, new dependency
installation or cross-platform test was run or claimed.

## Review boundary

The proposed exact-turn, reset and terminal semantics require human review before
integration. This work does not choose the scientific delay, model settings,
pressure, difficulty comparisons, held-out starts or evaluation protocol. A local
commit and review handoff are the milestone; GitHub publishing is a separate host
step. No push, merge, self-approval or project-roadmap update is part of this card.
