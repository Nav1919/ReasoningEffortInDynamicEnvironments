# Offline Freeway skeleton

This implements data validation for the scope in [weekly-tracker.md](weekly-tracker.md).
It makes no research claims and changes no milestones. No simulator adapter, model
client, policy, experiment, or empirical dataset is included. RealtimeGym has not
been installed or tested as part of this task. The tests use fictional data only.

From the repository root, using Python 3.10+ and the standard library:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B src/freeway_schema.py configs/freeway.json
```

`-B` prevents interpreter cache writes. No dependency installation is needed.
To validate future records, pass a JSON array file as the second CLI argument.
The CLI only reads inputs. It makes no network calls and writes no records.

## Configuration and seed manifest

[configs/freeway.json](../configs/freeway.json) is deliberately an incomplete draft.
Nulls, empty catalogs, and empty start lists mean unresolved decisions, not defaults.
`validate_manifest(..., ready=True)` rejects incomplete selections before records
can be accepted. Readiness here means schema completeness, not scientific approval.

The manifest fixes one exact `model_identifier`, `quick` and `deliberate` configuration
objects, difficulty and pressure catalogs mapping labels to exact setting objects,
an older-view delay in seconds, and separate development/held-out start lists.
Each start contains `start_id` and integer `seed`. IDs and seeds must be globally
unique, including across splits. Reuse the same entry for matched policy runs;
do not duplicate it in the manifest. Actual seed/replay semantics still need verification.
An exact simulator revision and verified settings must be recorded before real use
(for example as additional manifest metadata); this validator cannot verify replay.

## Decision record contract

[src/freeway_schema.py](../src/freeway_schema.py) exposes `validate_manifest` and
`validate_record`. Records are JSON objects; required fields are:

| Fields | Meaning |
|---|---|
| `schema_version`, `run_id`, `decision_index` | Version 1, nonempty run identifier, nonnegative integer decision index |
| `start_id`, `seed`, `split` | Exact manifest start; split is `development` or `held_out` |
| `model_identifier`, `mode`, `mode_configuration` | Frozen model, quick/deliberate label, exact corresponding settings object |
| `difficulty`, `pressure` | Labels in manifest catalogs; pressure alone is not evidence of traffic speed |
| `observation_time_seconds`, `action_time_seconds` | Observation capture and action submission on one monotonic clock |
| `observation_age_seconds` | Action submission minus capture; includes any deliberate delay and reasoning latency |
| `action`, `outcome` | Exact U/D/S; simulator-derived outcome object with adapter-defined raw fields |
| `input_tokens`, `output_tokens`, `reasoning_tokens` | Nonnegative integer provider measurements; document provider counting/overlap conventions |
| `elapsed_seconds` | Measured decision-call duration; not automatically equal to observation age |
| `failures` | List of nonempty failure explanations; empty on success |

Unavailable measurements, action, and outcome may be null only with a recorded
failure. Never substitute zero for missing token counts or silently drop failed runs.
Unknown reasoning-token counts must be recorded as unavailable, with an explanation.
No reward definition or token-count relationship is invented here. Failure records
still require start, configuration, and condition identity. Successful outcomes must
be objects, but their simulator semantics await verified integration.

Use `validate_record(record, manifest, purpose='development')` on development inputs:
it rejects held-out rows. The default `evaluation` purpose accepts either split for
read-only validation. This is an explicit caller contract, not access control or a
policy-freeze mechanism. Keep held-out records out of router tuning; the validator
cannot detect a human changing a manifest or tuning after viewing evaluation data.

## Blockers and human decisions

Stop before integration or experiments until people select the accessible frozen
model, exact quick/deliberate settings and prompts, affordable run counts, the two
difficulties, verified pressure controls, older-view delay, seeds/split allocation,
outcomes, and scientific analysis/freeze protocol. No choices are made here.

A future authorized environment task must verify RealtimeGym installation, revision,
actions, observation capture/action timing, simulator outcomes, pressure effects,
and repeatable starts using actual logs. Paid calls require separate authorization.
There are currently no observations, results, manipulation checks, or evidence of
Freeway reproducibility. Unit tests establish only the offline data contracts.
