# Freeway situation-bank pilot

This engineering pilot collects reachable checkpoints and computes exact bounded
action labels with the installed simulator. It makes no LLM calls. It is separate
from earlier pilot evidence and is not a held-out benchmark or evidence of model
improvement. No fabricated board states enter the bank.

## Run locally

From the repository root, use a new or empty output directory:

```sh
.venv/bin/python situation_bank.py collect --output data/situation_bank/freeway_pilot_v1
.venv/bin/python situation_bank.py label --output data/situation_bank/freeway_pilot_v1
.venv/bin/python situation_bank.py verify --output data/situation_bank/freeway_pilot_v1
.venv/bin/python -m unittest test_situation_bank -v
```

Collection defaults: 50 checkpoints, development selectors 0–4, three fixed
policies (forward-heavy, uniform random, waiting-heavy), at most 60 ticks per
trajectory, collection seed 473. Policy weights are ordered U, D, S. Snapshots
contain all environment attributes and the complete random-generator state.
Every checkpoint also contains a seed and action prefix for independent replay.
Selection cycles through initialization/lane/policy groups after seeded shuffling.
Exact physical configurations, including movement timers, are deduplicated across
candidates. Elapsed time is retained in snapshots but ignored for physical dedup.
This pilot does not promise balanced categories or full lane coverage.

The simulator accepts only eight easy-mode start selectors, not arbitrary integer
seeds. Production collection is restricted to the five existing development
selectors. An initial unsuccessful collection attempt encountered the eight-selector
limit after stepping selectors 5–7; none of those states is included in the saved
pilot. Treat those existing evaluation starts as exposed to this engineering work
when planning any future strictly untouched test set.

## What the answer key means

For each horizon 1–10 and each first action, complete bounded search finds whether
there exists a continuation that avoids collisions and survives the horizon, or
reaches the goal earlier. A collision disqualifies a branch even if the simulator
resets it. A timeout is not a safe completion. Each viable first action has a
witness sequence. Goal arrival is detected from the transition, including arrival
on tick 100, rather than inferred from score or an empty observation.

The objective is lexicographic: prefer reaching the goal, then minimize goal time;
if the goal is unreachable in the horizon, maximize final player progress among
surviving continuations. All tied best first actions are saved. This is bounded
optimality with a favorable continuation, not a guarantee under arbitrary future
actions or a full-game optimal policy. Failed branches have null outcomes.

Primary categories use this priority: must_retreat (only D has a safe continuation
at the maximum horizon); waiting_helps (immediate U collides but 1–3 stays followed
by U yields collision-free forward progress); safe_advance (U safely advances and
has a viable continuation); dangerous_advance (immediate U collides but an
alternative is viable); other. Waiting witnesses describe the short maneuver;
they do not independently guarantee survival to the maximum horizon.

## Saved files and checks

- `states.json`: IDs, collection provenance, raw observations, exact snapshots,
  replay prefixes, and state/dynamics hashes. Raw observations include both the
  simulator text drawing and its structured coordinate representation.
- `manifest.json`: settings, simulator source hash, data hash, and collection counts.
- `labels.json`: immediate transitions and safe/best actions and witnesses at
  each horizon. No oracle labels are added to model observations.
- `label_report.json`: category totals, horizon, search count, and labels hash.
- `validation_report.json`: replay, snapshot restoration, recomputed labels,
  and witness checks.
- `examples.json`: one compact representative per available category.

Verification rejects changed simulator source or changed data, reconstructs all
states independently from action prefixes, and replays every saved horizon/action
witness. Unit tests independently enumerate all action sequences through three
ticks and compare safe sets and every optimal tie against the memoized search.

## Before scaling to 500

The expanded collector below implements broader reachable-state exploration and
category-aware selection. Still needed before model experiments: audit observation
sufficiency, create equivalent renderers and explicit action-conditioned forecast
questions, and assign disjoint initialization and dynamics groups to
development/validation/test. Preserve an independently sampled live-play evaluation.
Neither saved bank implements those benchmark splits, traffic-only forecasts, or
a required-foresight metric.

## First local result

The default run produced 244 distinct candidates and selected 50: 40 safe-advance,
6 waiting-helpful, 2 retreat-required, 1 dangerous-advance and 1 other. Selected
states cover player lanes 0–6; lanes 7–8 are absent. All 50 snapshot/prefix pairs
agree, all labels recompute, and all 1,161 horizon/action witnesses replay.
Category imbalance and missing upper lanes require improved collection before
scaling. The other case has no collision-free immediate action.

For example, `freeway_0002` is at lane 5 on tick 53: U and S collide immediately;
D is safe and begins the collision-free goal-reaching sequence `DUUUUU` (6 ticks).
For `freeway_0003`, U collides immediately, but `SSU` safely makes progress.
At the starting boundary D and S can have identical effects, and tied first
actions are retained rather than labeling waiting as uniquely correct.

## Expanded 500-state development bank

```sh
.venv/bin/python situation_bank.py balanced --count 500 --ticks 89 --output data/situation_bank/freeway_bank_v2
```

This command collects, labels and verifies in one run. It preserves the original
50-state pilot. Instead of relying on random trajectories reaching the upper
lanes, it explores all three actions at each reachable state using breadth-first
search. Collision and terminal branches stop. Every retained state has an actual
collision-free action prefix from an unchanged development initialization. The
earliest visit to each physical configuration is retained, so repeated waiting
or collision resets cannot inflate diversity by changing only the episode clock.
States stop at tick 89, leaving enough time to label the full ten-tick horizon.
This is bounded exploration from five starts, not exhaustive enumeration of every
possible game initialization or of near-timeout situations.

The run found 2,938 distinct physical configurations. The measured candidate pool
contains 2,259 safe-advance, 321 waiting-helpful, 177 retreat-required, 18 remaining
dangerous-advance and 163 other situations. Selection initially targets 125 per
main category. When a category runs out, the remaining slots are distributed
across the available categories. Within categories, selection favors the least
represented player lane and then initialization; seeded shuffling breaks ties.
No situations are invented to meet the quotas, and other situations are excluded
from this diagnostic bank.

The saved 500 comprise 161 safe-advance, 161 waiting-helpful, 160 retreat-required
and 18 remaining dangerous-advance situations. Each position 0–8 has 55 or 56
states, and each actual initialization contributes 100. Primary categories are
mutually exclusive: waiting-helpful and retreat-required cases can also be
dangerous to advance, but are counted in their more specific categories first.

`candidate_inventory.json` records all candidate hashes and their category, lane
and initialization, making the available pool and selection shortfalls auditable.
The manifest records requested, available and selected category counts, exact
source hashes, coverage and selection settings. Search caches are shared across
states for speed; `search_states` counts newly computed cache entries, so it is a
performance statistic rather than an answer-key label. Verification compares
all semantic labels while ignoring that cache-dependent count.

This remains a development bank from five existing starts, with correlated
checkpoints and deliberate diagnostic sampling. It is not 500 independent games,
an untouched test set, or an estimate of natural live-play scenario frequencies.

Final checks passed for all 500 snapshot/prefix reconstructions and all 9,369
horizon/action witnesses. Semantic answer keys were recomputed successfully and
all 91 repository tests passed. The saved output includes a compact README and
one example per available category.
