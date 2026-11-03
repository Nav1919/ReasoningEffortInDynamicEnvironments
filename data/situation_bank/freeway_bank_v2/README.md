# Freeway: 500 saved development situations

Generated from 2,938 distinct reachable physical configurations using unchanged
development starts. Every saved situation has a replayable action prefix and a
full simulator snapshot. No model calls or synthetic board edits were used.

| Category | Saved states |
|---|---:|
| Safe advance | 161 |
| Waiting helps | 161 |
| Must retreat | 160 |
| Remaining dangerous advance | 18 |
| Total | 500 |

All player positions 0–8 have 55–56 states each; each of five initializations has
100. Categories are mutually exclusive: waiting and retreat cases take priority
over the broader dangerous-advance category. Only 18 cases remained in that last
category, so its 125-state target was not forced. The other slots were reassigned.

- [Saved states](states.json)
- [Answer keys](labels.json)
- [Compact examples](examples.json)
- [Settings and coverage](manifest.json)
- [All candidate hashes and categories](candidate_inventory.json)
- [Replay verification](validation_report.json)

Each answer key covers horizons 1–10, retaining all tied best first actions and
safe continuation witnesses. Goal arrival is preferred, then faster arrival;
otherwise the objective is greatest final progress along a surviving path.
Optimality is bounded to the horizon, not a full-game strategy guarantee.

Verification passed for all 500 restored/replayed states and all 9,369 saved
horizon/action witnesses; labels were independently recomputed from restored
states. All 91 repository tests passed, including independent short-horizon
exhaustive-search comparisons and deterministic collection checks.

These are correlated checkpoints from five starts, selected for diagnosis. They
are not 500 independent trajectories or an untouched test set. Use separate
initialization groups for later held-out model evaluation.

Reproduce from the repository root with a new output directory:

```sh
.venv/bin/python situation_bank.py balanced --count 500 --ticks 89 --output data/situation_bank/freeway_bank_v2
```

See [the protocol](../../../docs/situation_bank.md) for definitions and limits.
