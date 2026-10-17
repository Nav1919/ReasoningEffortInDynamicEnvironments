# Freeway fixed-situation and slower-clock study

The saved October 8 pilot is complete. The tables below are regenerated from
published historical records, not new model trials. See
[the portable evidence package](../evidence/freeway_20261008/README.md).

## Terms

The player position **y** is 0 in the starting area, 1–8 in the eight traffic
lanes, and 9 at the goal. **U** moves forward one lane, **D** moves backward one
lane, and **S** keeps the player in the same lane while traffic still moves.
A **valid response** is a completed response containing exactly one legal
action accepted by the existing strict parser: U/D/S after trimming whitespace
and normalizing case, with `done_reason="stop"`. Valid does not mean safe,
useful, or executed. Incomplete/prose responses are invalid. Live invalid
responses cause a separately logged S fallback; fixed-state diagnostics do not
execute fallbacks or count them as model choices.

A **crossing** is reaching y=9, not merely entering traffic. **Maximum position**
is the furthest position reached before the episode ends; it measures partial
progress. A **turn** is one environment step. A **waiting step** uses S because
no model response is ready. **Observation age** measures the time/turns between
the snapshot sent to the model and execution of its action. Turn age excludes
the action's own step. Second age includes waiting for the next tick after the
response arrives. **Latency** is the HTTP request duration. Median means the
middle measured duration; the 90th percentile is the duration at or below which
roughly 90% of requests fall (linear interpolation).

## Environment audit and prompt preservation

The installed environment is the sibling editable RealtimeGym checkout at
commit `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b`, whose status was clean. We read
`__init__.py`, `environments/base.py`, and `environments/freeway.py`. The current
difficulty remains `Freeway-v0`, which maps to E. Requested seeds 0,1,2,3,4 map
to actual seeds 1000,1001,1002,1003,1013. No environment code was changed.

The source confirms:

1. Reward decreases by one and the turn count increases on each step. The
   initial score is 100; there is no additional collision penalty.
2. The player moves first, clamped at the start/goal. Internal row `pos` counts
   downward, so observed y is `9 - pos`. The player crosses at internal column
   4, encoded as horizontal coordinate zero.
3. Reaching the goal ends the episode immediately, before traffic moves. The
   implementation then resets internal player position and returns an empty
   observation. A terminal U from observed y=8 proves success, including on
   turn 100. `done` or score alone does not prove a crossing.
4. Otherwise each car updates and its occupied integer cells are checked for
   a collision. Fast cars jump cells; swept paths are not checked. Slow cars
   use hidden timers. Structured car tuples contain lane, head coordinate,
   direction, nominal speed and length; coordinates are twelfths of a column.
   The structured head includes slow-car timer phase, and encoded length is
   `12 * occupied_cell_count - 1`.
5. Wrapping is delayed: if a car head is already outside columns 0–8 at the
   start of an update, it is placed at the opposite edge without another move
   that turn. This is not constant-speed modulo wrapping.
6. A collision sends the player to the start. Unless the episode has ended,
   it also resets traffic and the RNG to the seeded initial arrangement,
   preserving elapsed turns and score. At 100 turns the episode terminates.
7. The environment moves only when the runner calls `step`; it does not have
   a background game clock of its own.

The old prompt's statements about constant distance each turn, wrapping, and
unconditional traffic resets are simplified or overbroad. A separate named
`--prompt progress_source` variant corrects those points and clarifies the
immediate goal check. It is **not used in either requested comparison**. The
original and progress prompts, with full or structured observations, remain
byte-for-byte unchanged and selectable. This prevents a mechanics correction
from becoming an unrequested additional experimental factor.

## Experiment 1: fixed situations

**What changes:** prompt wording and, in a separate configuration, removal of
the text drawing. **Why:** test whether the model chooses useful actions when
its received state does not change during inference.

The compared prompts are:

- **Original/full:** existing instructions and both the text drawing and
  structured player/car values.
- **Progress/full:** adds an instruction saying the objective is to cross,
  staying forever loses at 100 turns, and S/D can be useful traffic choices.
  This instruction is text shown to the model, not a forced action.
- **Progress/structured:** the same added instruction, with only the redundant
  text drawing removed. All structured player/car values remain.

Fifteen distinct situations are selected without using model responses: five
safe-forward, five dangerous-forward, five waiting-useful. Each comes from
reset plus a saved deterministic action prefix on one of the five seeds. Fixed
random action tapes generate candidate trajectories; selection spreads player
positions across the road. No manually constructed state is queried. Repeated
player/car/timer layouts are excluded even if the turn or score differs.

Each saved situation contains seed mapping, action prefix, turn, complete
observation and internal state, including hidden car timers and the complete
NumPy RNG state. Every U/D/S test deep-copies the whole environment. Replay
checks and reversed-order tests verify that testing one action cannot alter
another test. Diagnostic construction actions and simulation reference answers
are never given to the live controller.

Criteria are deliberately limited:

- **Safe-forward:** U moves forward without a collision on the next step.
  U meets the progress objective; D/S may also be safe without progressing.
- **Dangerous-forward:** U collides on the next step and some other action
  avoids that collision. The acceptable set includes every one-step-safe
  action; avoiding U alone is insufficient if the chosen S also collides.
- **Waiting-useful:** a bounded sequence of S then U advances without any
  collision, while immediate U collides. All selected cases use horizon two:
  SU. All nine two-action sequences are tested for comparison. In four cases
  only sequences starting S achieve safe forward progress within that horizon;
  in one case D then U also works. This does not establish indefinite safety
  or an optimal whole-episode strategy.

For every situation/configuration the model sampling seeds are 0,1,2. The
**environment seed stays fixed** while sampling seed changes. Configuration
order rotates across situations. There are 135 measured requests, sequential,
with a separate warm-up before them. The environment remains fixed during the
request; returned actions are scored against the saved simulation outcomes.
Invalid responses remain separate and have no collision/usefulness outcome.

The original prompt still warns about asynchronous delay even though this
experiment freezes the state. Preserving that wording makes this a comparison
of the existing prompts, not a pure test with specially rewritten static-state
instructions. This limits conclusions about the model's underlying knowledge.

## Experiment 2: slower live environment

**What changes:** seconds per environment turn, 1, 2, or 4. **Why:** test whether
more time before the next traffic movement improves action execution.

Everything else remains fixed: progress/full prompt, thinking off, Qwen3
4B Q4_K_M, temperature 0.6, model sampling seed 0, context 4096 tokens, output
limit 2048 tokens, E difficulty, and 100-turn limit. The prompt explicitly
states its configured interval, so this experiment changes both actual time
pressure and the timing information supplied to the model. It cannot isolate
those effects. S remains the waiting action. No forced action, oracle, or
simulation reference guides live action selection.

The order is counterbalanced as closely as possible with five seeds:

| Requested seed | Actual seed | Interval order, seconds/turn |
|---:|---:|---|
| 0 | 1000 | 1, 2, 4 |
| 1 | 1001 | 2, 4, 1 |
| 2 | 1002 | 4, 1, 2 |
| 3 | 1003 | 1, 4, 2 |
| 4 | 1013 | 2, 1, 4 |

All 15 episodes run sequentially. Each warms the model before starting its
clock and waits for any late response before launching the next episode.
The actual command/order, start/end times and interruptions are recorded.
Slower intervals also mean longer wall-clock budgets: a 100-turn timeout takes
roughly 100, 200 or 400 seconds. The turn budget is unchanged.

The existing runner schedule is preserved:

1. Submit a request only when no request is pending and no ready action is
   waiting for a tick. Capture the current observation at submission.
2. Collect a finished response without stepping the game.
3. At the next tick apply a ready action once, or use waiting S if none is ready.
4. After consuming the ready action, request a new observation on the next loop
   iteration. Do not submit new requests while an earlier request is pending.
5. Schedule the next tick one configured interval after the previous step;
   do not issue catch-up bursts. Record scheduler lag.

Thus a 1.6-second request commonly arrives for the second 1-second tick, after
one waiting step. At 2- or 4-second ticks it may arrive before the first tick,
but execution still waits for that tick. These are timing illustrations, not
substitutes for measured observation ages.

## Provenance and local files

Evidence directory: `results/freeway_study_20261008T025226Z/`.
It contains exact requests/raw responses, diagnostic references, live JSON
logs and console logs, metadata, CSV/JSON summaries, a copy of the environment
source, and the source used for the study. The `before/` directory preserves
all four pre-existing changed files and their original Git status/diff.
No existing logs were overwritten. No applicable AGENTS.md files were found.

Ollama: 0.35.1. Installed model: `qwen3:4b-q4_K_M`, digest
`2bfd38a7daaf4b1037efe517ccb73d1a3bbd4822cf89f1a82be1569050a114e0`.
Full model metadata is saved, including parameter size and quantization.

## Measured fixed-situation results

All 135 responses were valid. The following counts each cover five situations times three sampling seeds: 15 requests. Collision counts are the actual next-step outcomes from the unchanged starting state, not delayed live outcomes.

| Prompt / observation | Situation category | Valid | U / D / S | Immediate collisions | Relevant choice |
|---|---|---:|---|---:|---|
| original / full | safe_forward | 15/15 | 0 / 1 / 14 | 4/15 | safe U: 0/15 |
| original / full | dangerous_forward | 15/15 | 0 / 0 / 15 | 6/15 | avoided U: 15/15 |
| original / full | waiting_useful | 15/15 | 0 / 1 / 14 | 0/15 | chose S: 14/15 |
| progress / full | safe_forward | 15/15 | 9 / 0 / 6 | 1/15 | safe U: 9/15 |
| progress / full | dangerous_forward | 15/15 | 10 / 0 / 5 | 11/15 | avoided U: 5/15 |
| progress / full | waiting_useful | 15/15 | 12 / 0 / 3 | 12/15 | chose S: 3/15 |
| progress / structured | safe_forward | 15/15 | 12 / 0 / 3 | 1/15 | safe U: 12/15 |
| progress / structured | dangerous_forward | 15/15 | 12 / 0 / 3 | 13/15 | avoided U: 3/15 |
| progress / structured | waiting_useful | 15/15 | 13 / 0 / 2 | 13/15 | chose S: 2/15 |

| Prompt / observation | Overall valid | Overall collisions | Median latency | 90th percentile latency |
|---|---:|---:|---:|---:|
| original / full | 45/45 | 10/45 | 0.090 s | 1.434 s |
| progress / full | 45/45 | 24/45 | 0.097 s | 1.532 s |
| progress / structured | 45/45 | 27/45 | 0.091 s | 0.982 s |

The original prompt never chose U in the safe-forward group. Its preference
for S is not proof of safety: it caused 10 collisions across 45 choices,
including situations where the player needed to leave its current lane.
The progress instruction raised safe-forward U choices from 0/15 to 9/15,
but selected U in 10/15 dangerous-forward queries and 12/15 waiting-useful
queries. Removing the board increased safe-forward U to 12/15 while also
increasing dangerous U choices. This supports a shift toward forward movement,
not reliable recognition of traffic hazards. All outputs were syntactically
valid, so these failures were action-selection failures rather than parser or
completion failures.

Waiting was chosen in 14/15 original-prompt queries, 3/15 progress/full queries,
and 2/15 progress/structured queries. These are first-action choices only:
the model was not asked to produce or execute SU. A first S is compatible with
the verified two-turn reference; it does not prove the model would then choose U.

The short median diagnostic latency needs care. With sampling seed 0 (the
first pass over each situation's prompts), median request time was 1.295 s and
median server prompt-evaluation time was 1.243 s. With seeds 1 and 2, median
request times were 0.090 and 0.088 s, and prompt evaluation was about 0.034 s.
These server measurements are consistent with reuse of cached prompt work;
cache reuse is an interpretation, not a directly inspected implementation.
The 0.09-second diagnostic median must not be treated as the expected live
latency for changing observations. No model requests ran concurrently.

### Concrete diagnostic examples

1. **Move out of danger by advancing** (`safe_forward_seed1`, actual seed
   1001, turn 9, y=2). U advances to y=3 without collision. S leaves the player
   in the lane where it is hit and reset to y=0; D also collides. At sampling
   seed 0 the original prompt chose S and failed, while both progress prompts
   chose U and safely advanced. Across three sampling seeds, the original
   chose S three times; each progress variant chose U, S, U, succeeding twice
   on the immediate-action criterion.
2. **Retreat is necessary for this step** (`dangerous_forward_seed2`, actual
   seed 1002, turn 17, y=3). U enters a collision and resets to y=0. S also
   causes a collision. D retreats to y=2 without collision. The original
   prompt chose S for all three sampling seeds; both progress variants chose
   U for all three. All nine choices collide despite the state remaining
   fixed during inference. Merely avoiding U was not enough here.
3. **A short wait opens a lane** (`waiting_useful_seed1`, actual seed 1001,
   turn 0, y=0). Immediate U enters lane 1 just as traffic moves across the
   crossing point and causes a collision. S on the first turn leaves the
   player at y=0 while the car passes; U on the second turn safely reaches
   y=1. D then U gives the same outcome because D is clamped at the start.
   The original prompt chose S on all three queries, compatible with waiting;
   both progress variants chose immediate U on all three and collided. This
   is a concrete prompt disagreement, not evidence that S is uniquely optimal.

These results do not establish the model's internal reasoning process. A
plausible hypothesis is that the prompts shift its preference toward S or U
without sufficiently changing its traffic prediction. The observed evidence
is the action distribution and simulated next-step outcomes, not that hypothesis.

## Reproduction and code changes

Use the project's `.venv` Python with the local Ollama server already running.
Choose a **new** output folder for each replication; existing raw logs are
intentionally protected against overwriting.

```sh
.venv/bin/python -m unittest test_model_freeway.py test_freeway_study.py
.venv/bin/python -m py_compile run_model_freeway.py freeway_study.py test_freeway_study.py
.venv/bin/python freeway_study.py diagnostics --output results/freeway_replication_01
.venv/bin/python freeway_study.py live --output results/freeway_replication_01
.venv/bin/python freeway_study.py summarize --output results/freeway_replication_01
```

The measured run used a single sequential command:

```sh
.venv/bin/python freeway_study.py all --output results/freeway_study_20261008T025226Z
```

To reproduce one episode outside the sweep:

```sh
.venv/bin/python run_model_freeway.py --prompt progress --board full --thinking off --seed 0 --model-seed 0 --tick-seconds 2
```

This task changes/adds these source/document files:

- `run_model_freeway.py`: small additions for sampling-seed selection, a
  protected explicit log path, observation/execution timestamps, completion
  reason/token fields, and separately selectable mechanics-corrected prompt.
  The original schedule, parser, default action, old prompts and defaults stay
  intact. The earlier uncommitted warm-up and logging improvements are preserved.
- `freeway_study.py`: reproducible situation generation, independent action and
  bounded-sequence simulation, exact diagnostic requests, sequential matched
  live runs, run manifest, per-episode/interval/paired JSON and CSV summaries.
- `test_freeway_study.py`: reproducible state replay, independent simulations
  including reset/RNG behavior, shared sampling-seed isolation, parser checks,
  terminal-goal interpretation, percentile convention and matched-order checks.
- `docs/freeway_timing_study.md`: this report.
- `results/freeway_study_20261008T025226Z/`: local raw evidence, machine-readable
  summaries, source snapshots and backups. Nothing here is staged or committed.

The pre-existing `diagnose_freeway.py`, `test_model_freeway.py`, and
`docs/freeway_diagnosis.md` were inspected and left unchanged. The new study
script supplements the earlier four-state diagnostic rather than replacing it.
Eight relevant tests passed, as did Python compilation and `git diff --check`.
An explicit comparison to the saved pre-task runner verified byte-for-byte
identity of the existing prompt variants.

## Verified saved live results (publication audit)

All 15 manifest entries are complete, covering five matched starting seeds at
each interval. No failed episode was removed from this manifest. The published
logs retain late responses and invalid-response fields, including zero observed
invalid responses in this live sweep.

| Seconds/turn | Crossings | Mean maximum y | Total collisions | Waiting steps | Median age in turns | Median latency |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0/5 | 4.4 | 76 | 224 | 1 | 1.217 s |
| 2 | 2/5 | 4.6 | 94 | 3 | 0 | 1.049 s |
| 4 | 2/5 | 6.0 | 90 | 0 | 0 | 1.150 s |

Requested seeds 0 and 3 crossed at both slower intervals; the other three did
not. Slower ticks largely eliminated inference waiting, but did not reliably
solve action choice. Collision totals cover differing episode lengths (500,
361, and 347 total turns); they are not equal-exposure collision rates.
Zero turn-age means no intervening game movement, not zero elapsed seconds:
median second-age was approximately 2.003, 2.001, and 4.001 seconds.
Five starts per condition are preliminary evidence without uncertainty estimates
or held-out evaluation. Timing information in the prompt and longer wall-clock
budgets also change with the interval, limiting causal interpretation.

The publication checks replay all 15 saved action sequences and regenerate all
four summary pairs after relocating the evidence directory. This verifies saved
transitions and aggregation; it is not a new model-quality experiment.
The original `results/` directory stays local. The portable `evidence/` package
normalizes paths, compresses episode JSON, and records the transformation and
original hashes. Earlier references in this report describe historical local
paths and source changes, not a claim that every backup/console file is published.

## Publication verification — October 17, 2026

Existing tests ran first (8 passed). After adding portability/replay checks,
11 tests passed in both the existing environment and a new isolated environment.
The documented `pip install -r requirements-freeway.txt` completed in that fresh
Python 3.13.2 environment; `pip check` found no broken requirements. Its installed
RealtimeGym was a built package, rather than the existing editable sibling checkout.
All 15 historical live trajectories replayed, and relocated regeneration matched
each saved JSON/CSV summary. Regenerated numerical results also matched the
original local tables before packaging. Python compilation and diff whitespace
checks passed. The offline scripted smoke produced 100 turns / 25 collisions and
its newly saved actions replayed successfully.

One new `freeway_study.py smoke` call against the already installed local model
returned valid U in 5.689 seconds. It was a frozen-state connectivity check, not a
new study trial; its record is in ignored `logs/publication_smoke_20261017/`.
No large experiment, model download, paid API call, router, or schema integration
was performed. Cross-machine/OS installation and new full inference replication
remain untested. The final merge requires an actual teammate's approval.
