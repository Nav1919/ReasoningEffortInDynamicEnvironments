# Strict matched quick-versus-deliberate analysis

**Status:** supporting offline interface proposed for human review, not an adopted
experiment protocol or completed benchmark. Existing October pilot records are
not a completed quick/deliberate comparison and are not automatically converted.
No model selection, budgets, frozen settings, splits, or outcome definitions are
changed here. Model identity and declared settings must come from the approved
run manifest; this tool cannot verify their truth against a model server.

## Task contract

- **Hypothesis:** this supporting milestone can be implemented and independently
  checked offline without changing approved scientific choices.
- **Dependencies:** baseline `22cdee9`, Python standard library. Full regression
  tests also use the provisioned RealtimeGym revision
  `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b` and its existing dependencies.
- **Acceptance:** strict matching, duplicate/configuration rejection, retained
  failures/missing coverage, correct signed differences, JSON/CSV round trips,
  both repository test discovery commands passing in the pinned Python runtime.
- **Artifacts:** [implementation](../../paired_comparison.py),
  [synthetic tests](../../test_paired_comparison.py), this interface document;
  user-selected JSON report and optional CSV table paths at execution time.
- **Seed/config manifest:** no research runs. Test scenarios, seed labels, budgets,
  outcomes and costs in `synthetic()` are explicitly synthetic. Actual analysis
  requires explicit start identity and shared/mode settings copied from approved
  records. No inferred defaults, held-out tuning or fresh model measurements.
- **Compute allowance:** local offline CPU tests only; existing coding-assistant
  subscription authorized. No installs, network, inference or paid experiments.
- **Stop condition:** tested local commit and human-review handoff; no publishing,
  self-approval, merge, or scientific conclusion.

## Run and test

From the repository root:

```sh
/usr/bin/python3.13 paired_comparison.py runs.json --output comparison.json --csv-output pairs.csv
/usr/bin/python3.13 paired_comparison.py runs.csv --output comparison-from-csv.json
/usr/bin/python3.13 -m unittest test_paired_comparison -v
```

The CLI reads the full input and validates before writing. Input and output paths
must be distinct. Parent directories must exist. Output paths are overwritten;
choose fresh paths to preserve earlier analyses. Invalid input exits nonzero.
The JSON report is authoritative: it includes original records, coverage and
pairs. The optional flat CSV has one row per controlled start, mode statuses,
mode measurements, evidence-kind labels and signed differences; nulls become empty cells. CSV alone
is not a full provenance/coverage report. Outputs are not transactionally written
as a set: a filesystem error can leave a partial set; preserve it as failure evidence.

## Input schema (version proposed here)

JSON is a nonempty array of records; CSV uses exactly the same named columns,
one record per row. Every field is required, unknown fields and duplicate JSON
keys/CSV columns are rejected. All
CSV identifiers remain strings; settings cells are JSON objects and metric cells
are JSON numbers, `null`, or empty. CSV must use normal quoting for embedded JSON.

| Field | Required meaning |
|---|---|
| `scenario` | Nonempty string identifying the exact scenario definition/version |
| `start` | Nonempty string identifying recorded seed/game situation, including replicate if applicable |
| `difficulty` | Nonempty exact difficulty setting identifier |
| `pressure` | Nonempty exact measured pressure condition identifier |
| `observation_condition` | Nonempty exact observation/delay/refresh condition identifier |
| `model_identity` | Nonempty exact frozen model identity/version (one per analysis) |
| `mode` | Exactly `quick` or `deliberate` |
| `shared_settings` | Nonempty JSON object recording all other controls: e.g. simulator revision, actual seed/state hash, prompt hash, sampling seed/temperature, timing, outcome definition and token accounting definition |
| `mode_settings` | Nonempty JSON object containing the declared reasoning/output settings; stable within each mode across the entire analysis, distinct between modes |
| `status` | Exactly `completed`, `failed`, or `missing` |
| `error` | Empty string for completed; explicit failure/absence reason otherwise |
| `outcome` | Finite numeric scalar in a consistently defined unit; required for completed, otherwise numeric or null |
| `seconds` | Nonnegative finite measured seconds or null; never inferred from token counts |
| `tokens` | Nonnegative integer measured token count or null; use one declared accounting definition |
| `evidence_kind` | Exactly `synthetic` or `measured`; mixing is rejected |

A `missing` placeholder must have all metrics null. A `failed` run can retain
partial measurements, including recorded cost, but these do not enter paired
differences. A completed run may lack time/token instrumentation: keep null,
not zero. Outcome is a scalar supplied by the approved evaluation, not an LLM
judge or a definition chosen by this script. Numeric differences do not imply
that larger outcome is scientifically better.

### Matching and conflicts

The identity is `(scenario, start, difficulty, pressure, observation_condition,
model_identity, mode)`. Duplicate identities, including retries, are errors; an
analysis must explicitly resolve retries upstream without silently discarding
failure evidence. Repeat identifiers must reflect genuine planned replicates,
not hide unmatched starts.

Pair only records whose six control fields match exactly and whose modes differ.
Shared settings must match structurally within each pair (object key ordering is
irrelevant). Conflicting per-mode settings anywhere in a file are rejected; the
mode labels must represent distinct declared settings. One model and one evidence
kind are required per analysis. Different difficulty/pressure/observation/start
identifiers produce separate cells, **never** a cross-condition pair. No fuzzy
matching, implicit pilot adaptation, case normalization or seed guessing occurs.

Callers are responsible for recording all scientific controls accurately in
`shared_settings`, and only approved reasoning differences in `mode_settings`.
This generic offline interface does not determine which scientific fields may
vary, validate manipulation checks, reserve held-out starts or authorize a run.

## Coverage and arithmetic

The denominator is the union of explicit controlled starts in the input, not an
assumed experiment grid. For each start, an absent counterpart is counted as
missing and has null measurements. To include a start where **neither** mode ran,
provide a missing placeholder (preferably for both modes) with its planned
controls/settings and an absence reason. Without an external planned manifest,
unrepresented starts cannot be detected; this is not completeness certification.

`coverage` reports input records, controlled starts, completed pairs, per-mode
completed/failed/missing counts (including inferred missing counterparts), and
usable pair counts separately for outcome/seconds/tokens. All explicit records
remain in `records`, including failures and missing placeholders. Per-start
`pairs` contain both statuses and recorded metric values.

Each `*_difference` is **deliberate minus quick**, only when both records completed
and both corresponding measurements are nonnull. Otherwise it is null, never an
imputed zero. No aggregate significance, uncertainty interval, superiority claim,
or pooled condition average is calculated. A failed run's costs remain visible
but do not become a misleading completed-run comparison.

## Synthetic example

To exercise the CLI without inventing model evidence, generate the exact labeled
unit fixtures in a fresh scratch directory and run the analysis:

```sh
/usr/bin/python3.13 -c 'import json; from test_paired_comparison import synthetic; print(json.dumps([synthetic(), synthetic("deliberate")]))' > /path/to/scratch/synthetic-runs.json
/usr/bin/python3.13 paired_comparison.py /path/to/scratch/synthetic-runs.json --output /path/to/scratch/synthetic-report.json --csv-output /path/to/scratch/synthetic-pairs.csv
```

Synthetic differences are outcome `2`, seconds `3`, tokens `20`, with one
completed pair. These numbers are software assertions, **not** model results.
Tests also exercise losses, ties, mismatched controls, failures, missing starts,
missing instrumentation, invalid schemas/nonfinite numbers and subprocess CLI
success/failure. The handoff records actual complete-suite commands and results.

## Local validation — October 30, 2026

Executed in the assigned isolated branch/worktree on `/usr/bin/python3.13`
(Python 3.13.5), using the provisioned dependencies without installations:

```sh
PYTHONPATH=/opt/data/research/freeway/source/src:/opt/data/research/freeway/site-packages SDL_VIDEODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 /usr/bin/python3.13 -m unittest discover -v
# Final result: 24 tests passed (includes 10 synthetic comparison tests).
PYTHONPATH=/opt/data/research/freeway/source/src:/opt/data/research/freeway/site-packages SDL_VIDEODRIVER=dummy PYGAME_HIDE_SUPPORT_PROMPT=1 /usr/bin/python3.13 -m unittest discover -s tests -v
# Result: 7 smoke tests passed.
git diff --check
# Passed.
```

The first comparison-only run passed 9 tests; a duplicate-JSON-key regression
was then added. Root discovery passed first with 23, then with 24 tests after
hardening; the final 24-test run includes strict required CSV columns. No test
command failed. CLI malformed-input tests intentionally assert nonzero exits.
No fresh inference, paid experiment, network operation, held-out evaluation or
cross-platform installation was run. Subscription token/cost telemetry was not
available to this worker; no measurement is invented. Scientific configuration
approval, full planned-grid completeness and real benchmark conclusions remain
outside this supporting implementation. GitHub publishing is a separate host
step after human review; nothing was pushed or merged here.
