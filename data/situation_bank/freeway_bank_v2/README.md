# Freeway development bank: run summary

The generator selected 500 situations from 2,938 reachable configurations.

| Category | States |
|---|---:|
| Safe advance | 161 |
| Waiting helps | 161 |
| Must retreat | 160 |
| Remaining dangerous advance | 18 |

Each player position 0–8 has 55–56 states; each of five starts contributes 100.
Waiting and retreat cases take priority, leaving only 18 in the last category.
These are related development checkpoints, not independent games or test data.

Review [four small examples](examples.json), [settings and coverage](manifest.json),
[answer-key counts and checksum](label_report.json), and [replay results](validation_report.json).
For example, `freeway_0002` is at lane 7 on tick 59: up and stay collide,
while down followed by three ups reaches the goal safely.

All 500 states and 9,369 saved solution sequences passed replay checks.
The full datasets are preserved locally but excluded from Git. See the
[run instructions](../../../docs/situation_bank.md) to regenerate them.
