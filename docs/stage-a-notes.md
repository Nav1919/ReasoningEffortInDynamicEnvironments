# Stage A: technical notes

We want to find out which format helps small language models read Freeway most
accurately, and whether the answer changes with model size. Our hypothesis is
that explicit positions may help more than ASCII. We have not tested that yet.

## What this change adds

`freeway_observations.py` takes a saved game observation and shows it in six
formats: ASCII, coordinates, prose, a table, player-relative offsets, and JSON.
Each format includes every car's ID, lane, position, direction, speed and length.
The ASCII view also lists exact values because the grid alone loses detail.

Inputs exclude hidden timers, random-generator state, future positions and
answer keys. The bank stays unchanged. IDs apply within each saved situation.

## The data we use

The local file is `data/freeway_scenarios.json`. It contains 500 distinct
situations: 161 safe advances, 161 where waiting helps, 160 requiring retreat,
and 18 other dangerous advances.

These come from five development starts, not 500 independent games. Each actual
start—1000, 1001, 1002, 1003 and 1013—contributes 100 situations. Collection uses
seed 473, up to 89 ticks, and a ten-tick action-scoring horizon.

Start selectors 0–7 have already been used. We still need to check past usage
and reserve genuinely unused starts for the final evaluation.

## How positions work

The player stays at x=0. Lane 0 is the start, lanes 1–8 contain traffic, and
lane 9 is the goal. Column j maps to x=`12*(j-4)`, plus simulator position detail.
A rightward tail is head minus length; a leftward tail is head plus length.

Direction and speed come from the simulator's observation. They are not inferred
from a picture. All six formats receive them.

The drawing does not determine collision safety. The simulator moves the player,
handles goal arrival, then moves cars and checks collisions. Hidden timers affect
movement, and cars can briefly extend off the board before returning at an edge.

## Checks and limits

Acceptance: repeatable previews, all car facts retained, correct boundaries,
no hidden answers, and an unchanged bank.

Original implementation checks:

- All 500 situations and 9,369 saved action sequences replayed successfully.
- All nine relevant unit tests passed.
- All 500 situations rendered in six formats, retaining every car ID.
- The bank checksum stayed unchanged; the relative-format preview succeeded.
- `git diff --check` passed.

One command failed with exit 127 from the wrong folder, then passed from the
worktree. The full suite was not run. Complete information equivalence still
needs stronger tests.

## Run it

Use Python 3.13.2 and the existing project environment. Replay uses Freeway
revision `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b`; rendering needs only Python's
standard library. From this isolated worktree:

```sh
../../.venv/bin/python -m unittest test_freeway_observations test_freeway_scenarios -v
../../.venv/bin/python freeway_observations.py --file ../../data/freeway_scenarios.json --id 0
```

## What comes next

Agree on distance, radius, occupied-cell definitions, position targets, ties,
empty answers and uncertainty estimates. Add stronger information-preservation
tests and simulator-checked perception answers before running the experiment.

The later action check will reward the fastest safe crossing, or the most safe
progress within ten ticks, accepting tied best actions. It tests decision-making
as well as perception.

The proposed Qwen3 1.7B/4B/8B/14B comparison still needs hardware checks, exact
model/settings records, a format-selection rule and an approved call budget.
Earlier frozen model settings stay unchanged.

Budget: local CPU checks only, zero inference/API spend. Stop at input-layer
changes; experiments need approval. No format is selected and no model results
or figures exist yet.
