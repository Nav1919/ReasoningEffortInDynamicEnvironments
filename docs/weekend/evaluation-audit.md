# Held-out evaluation audit — proposed interface

This is supporting code for human review, **not an adopted evaluation protocol**.
It does not choose starts, conditions, policies, model, run count or outcomes.
Owners must approve those scientific choices separately. Historical pilot logs
are not in this format and have no held-out validation; nothing here converts
or upgrades them into held-out evidence.

## Task contract

- **Hypothesis:** offline completeness checks can detect broken comparison inputs
  without changing the frozen model or approved scientific choices.
- **Dependencies:** Python standard library; existing baseline `22cdee9`.
  The full regression suites additionally use the provisioned pinned simulator.
- **Acceptance:** explicit frozen digests, split disjointness, complete matched
  cells, retained failures/duplicates, local source integrity, deterministic
  JSON/text reports, meaningful synthetic corruption tests and both existing
  discovery suites passing. No experiment outcome is an acceptance criterion.
- **Artifacts:** [auditor](../../evaluation_audit.py),
  [tests](../../test_evaluation_audit.py), this interface proposal and the README
  navigation entries. Reports go to stdout; callers can redirect into **new**
  files outside saved evidence. No real audit bundle is supplied or selected.
- **Seed/config manifest:** callers provide the explicit bundle below; all unit
  test starts, negative seeds, policies, models and source bytes are synthetic.
  No real held-out starts were selected and no model was run.
- **Compute allowance:** offline CPU unit tests only, provisioned Python 3.13;
  no installs, network, downloads, paid experiments or inference. Coding-assistant
  subscription authorized; token/cost telemetry unavailable here.
- **Stop condition:** tested local commit and human-review handoff, not merge,
  publishing, scientific approval or experimental success.

## Run or import

```sh
/usr/bin/python3.13 evaluation_audit.py /path/to/bundle.json \
  --source-root /path/to/source-snapshots --format json
/usr/bin/python3.13 evaluation_audit.py /path/to/bundle.json \
  --source-root /path/to/source-snapshots --format text
/usr/bin/python3.13 -m unittest test_evaluation_audit -v
```

`audit(bundle, source_root)` returns the same JSON-compatible report in memory;
`human_summary(report)` renders it. `config_digest(value)` is the public digest
helper. CLI exit codes: **0** structurally complete, **1** refused comparison,
**2** unreadable/invalid JSON or command-line error. Duplicate JSON object keys
and non-finite numbers are refused. Malformed bundle shapes produce a JSON/text
refusal report; malformed JSON produces a stderr diagnostic instead.

The auditor reads only the bundle and explicitly referenced local files. It does
not use the simulator, call a model, repair evidence, select retries, compute
performance statistics or write files. Do not redirect stdout over input evidence.

## Version 1 bundle (proposed)

Every object below is supplied by the caller, never inferred from observed
performance. Unknown extension fields are allowed but do not relax required
fields. JSON objects use string keys. IDs must be nonblank strings.

| Field | Required value |
|---|---|
| `schema_version` | Integer `1` (not boolean) |
| `frozen_config` | Nonempty object with nonempty `model`, `settings`, `modes` objects; include exact model/artifact identity, shared settings and both approved reasoning-mode definitions |
| `frozen_config_digest` | Digest of the entire `frozen_config` |
| `policies` | Nonempty map from policy ID to nonempty frozen rule/config object, including allowed inputs and thresholds as appropriate |
| `policy_digests` | Map with exactly the same policy IDs, each digesting the corresponding policy object |
| `conditions` | Nonempty map from condition ID to nonempty exact environment/settings object |
| `starts` | Nonempty map from start ID to nonempty identity object: actual seed, initial-situation identity and any other initialization controls |
| `splits` | Exactly `development` and `held_out`, each a nonempty list of declared start IDs; every start belongs to a split |
| `sources` | Exactly `runner`, `simulator`, `policies`, each a source reference with a nonblank `revision` |
| `episodes` | List of episode metadata objects; empty lists are reported as entirely missing coverage |

A source reference is `{"path": "relative/file", "sha256": "<64 lowercase hex>"}`.
The three source roles additionally require `revision`, an explicit version or
commit identifier. Each role should point to the complete relevant source
snapshot/archive, not an arbitrarily chosen file. A combined policy snapshot
covers all declared policies. Referenced files must exist below `--source-root`;
absolute paths, escaping symlinks, missing files and wrong checksums are refused.
All paths are interpreted relative to that root, not the bundle's directory.

### Digest definition

Lowercase SHA-256 of the UTF-8 encoding of:

```python
json.dumps(value, sort_keys=True, separators=(',', ':'),
           ensure_ascii=False, allow_nan=False)
```

Use the provided helper; no cross-language number normalization is promised.
Changing a numeric representation, model, setting, rule or initialization field
changes its digest. Object-key order does not. Digests are checksums, not digital
signatures or proof of when a configuration was frozen.

### Episode metadata and raw files

Each episode requires:

- Unique nonempty `episode_id` and a `start_id`, `condition_id`, `policy_id` naming
  one expected held-out cell.
- `status`: only `completed` is accepted; failed, aborted, missing or any other
  value blocks comparison. Completed means recorded execution finished, **not**
  that the agent crossed successfully. Preserve failures rather than deleting
  or replacing them. No outcome is interpreted by this gate.
- Full `frozen_config`, `start`, `condition`, `policy` objects and their explicit
  `frozen_config_digest`, `start_digest`, `condition_digest`, `policy_digest`.
  Payloads and digests must match the manifest, not merely agree with each other.
  This allows different policies/modes while requiring the same model, shared
  settings and available reasoning-mode definitions.
- `source`: a local JSON episode source reference. Its decoded object must equal
  **all** metadata fields of this episode except `source` itself. Extra fields,
  such as outcomes or failure reasons, must also match. A correct checksum on
  an unrelated raw file does not pass. Distinct episodes must use distinct
  resolved source paths; shared archive files are not episode files.

The raw episode format is intentionally a proposed envelope, not the historical
pilot format. Source metadata is checked against bytes and the caller's manifest;
no legacy adapter is silently applied. Caller extensions may retain full traces.

### Expected coverage and refusals

Expected cells are the complete Cartesian product:

`held_out start IDs × condition IDs × policy IDs`.

Each cell requires **exactly one** completed episode. Repetitions must already be
encoded in caller-approved start identity (e.g. sampling seed/replicate), not
silently deduplicated or averaged. Unexpected/development episodes are refused
and never fill a held-out cell. Duplicate IDs, duplicate cells, reused raw paths,
missing cells and failed episodes are all blocking issues. Every expected cell
appears in `coverage`, with `recorded` and `completed` counts, including zeros.
These counts describe submitted statuses; a completed cell with invalid config
or provenance is still refused through `issues`.

The two splits must be disjoint by full canonical start identity, not just ID.
Identical start payloads under different IDs are detected both within a split
and across splits. The caller must include every scientifically relevant
initialization field consistently: this check cannot detect two physically
identical states encoded differently or undisclosed development usage.

## Reports and interpretation

JSON contains `schema_version`, `comparison_allowed`, `expected_episodes`,
`recorded_episodes`, `coverage`, and `issues`. Each issue has `code`, `location`
and `detail`. The text format shows the same gate decision, counts, cell coverage
and issues. Ordering is deterministic for a given bundle and source root.

`comparison_allowed: true` means only these structural and byte-integrity checks
passed. It is **not** permission to assert a scientific improvement: the auditor
cannot establish honest freeze timing, absence of tuning, completeness of source
archives, correctness of declared revisions, actual loaded model identity,
correct outcomes/costs, simulator replay, statistical uncertainty or protocol
approval. It trusts the caller's declared expected population and configuration.
A SHA-256 can detect changed bytes, not prove trustworthy origin. An incomplete
or dishonest caller manifest is not repaired by an audit. Those limitations need
human review and independent replay/provenance checks.

## Validation record

Initial targeted run: 13 tests, one failure in the test helper because explicit
`None` was treated as the default valid fixture. Replaced that default with a
sentinel; this was a test-helper defect, not a missing run or experiment result.
Final pinned-runtime checks and commit identity are recorded in the card's human
review handoff. All fixtures are explicitly synthetic and temporary. No existing
evidence was changed, no held-out selection/tuning occurred, and no experiment
result is claimed. GitHub publishing remains a separate host step.

Executed on Python 3.13.5 in the assigned isolated worktree:

```sh
/usr/bin/python3.13 -m unittest test_evaluation_audit -v
# 13 passed after the initial helper correction; one multi-start test added later.

PYTHONPATH=/opt/data/research/freeway/source/src:/opt/data/research/freeway/site-packages \
SDL_VIDEODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 \
/usr/bin/python3.13 -m unittest discover -v
# Final: 28 passed, 4.742s (14 synthetic audit tests + 14 existing tests).

PYTHONPATH=/opt/data/research/freeway/source/src:/opt/data/research/freeway/site-packages \
SDL_VIDEODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 \
/usr/bin/python3.13 -m unittest discover -s tests -v
# 7 passed, 0.879s, including independent-process simulator repeatability.

git diff --check
# Passed.
```

The earlier full discovery run also passed (27 tests, before the added explicit
multi-start coverage case). No real held-out audit, inference or new installation
was run; these are not missing successful experiments. Synthetic complete/refused
JSON and text examples were generated locally for the review handoff, outside the
repository. Hermes/Codex assisted implementation and validation; human review is
still required.
