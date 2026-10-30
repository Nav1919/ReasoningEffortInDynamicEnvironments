# Proposed explicit experiment manifest

This is a portable, offline **interface proposal**, not an approved scientific
configuration, experiment runner, or adoption of deferred PR #5. Historical logs
and evidence remain unchanged. Owner approval through Discord is still required
for scientific choices or protocol changes. No model, thresholds, split, run
count, or compute budget is selected here.

## Task contract

- **Hypothesis:** explicit configuration and matched-control mistakes can be
  independently detected offline without changing scientific choices.
- **Dependencies:** Python standard library only for the validator/tests. Full
  repository checks additionally use the provisioned RealtimeGym revision
  `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b` and its existing dependencies.
- **Acceptance checks:** reject incomplete identities, malformed fields,
  overlapping/duplicate split seeds, ambiguous mode overlays, and mismatched
  comparison controls; exercise the CLI and existing offline discovery suites.
- **Artifacts:** [validator](../../experiment_manifest.py),
  [tests](../../test_experiment_manifest.py), this interface note and additive
  README navigation. No experiment results are produced.
- **Seed/config manifest:** no scientific manifest is supplied. Tests use clearly
  synthetic values only; these are not recommended settings or reserved starts.
- **Compute allowance:** offline validation/tests and authorized coding-assistant
  subscription only; no installs, downloads, network, model inference or paid
  experiments. Scientific run budgets must be separately supplied and approved.
- **Stop condition:** tested local commit and human-review handoff, without
  publishing, merging, approving, or running a scientific experiment.

## Required JSON interface

Every top-level field below is required. Fixed-structure objects reject unknown
keys so misspelled controls cannot be silently ignored. There are no defaults.

| Field | Explicit caller input |
|---|---|
| `frozen_model` | Object with nonempty `name` and `revision` strings identifying the same frozen weights/version across modes. Supply an immutable digest or equivalent identity, not just a floating model tag. |
| `simulator` | Object with nonempty `name` and `revision` strings identifying the simulator source. |
| `environment` | Object with nonempty `name` and a nonempty `difficulty` settings object recording the exact chosen parameters. |
| `pressure` | Object with nonempty `control`, `units`, and `semantics` strings plus an explicit non-null JSON `value`. Explain the actual setting, timing/advance behavior and what it does **not** establish. |
| `common_settings` | Nonempty JSON object of identical non-mode controls: record prompt/version, decoding/sampling controls, observation/action timing, termination limits and other applicable controls explicitly. |
| `modes` | Object containing exactly `quick` and `deliberate`, each a nonempty settings object with the same keys but distinct values. Record the backend's exact reasoning/output-budget settings; no mode key may override a `common_settings` key. |
| `active_mode` | Exactly `quick` or `deliberate`. Both mode definitions are still required. |
| `seeds` | Object containing exactly `development` and `held_out`: nonempty lists of unique integers (not booleans), disjoint across splits. Order is retained as a comparison control. |
| `output_path` | Nonempty path string without NUL, explicitly chosen by the caller. |

Settings accept finite JSON values (including nested objects/lists); the validator
cannot infer backend-specific parameter names, ranges, semantics, seed namespaces
or effective overrides. `common_settings` must include all applicable non-mode
controls, including sampling seeds separately from environment starts when used.
Do not put model selection, prompt changes or other confounds in mode settings.
Difficulty parameters and pressure controls are recorded, not scientifically
validated. The validator cannot prove that identity strings are immutable, inspect
weights/source, detect previous held-out exposure, verify approvals/budgets, or
establish that pressure alters volatility. Review those scientific facts separately.
Passing validation is not permission to run an experiment.

## Offline use

Prepare your own reviewed JSON file using the fields above. No runnable scientific
template is provided, to avoid silently selecting values.

```sh
python experiment_manifest.py /path/to/explicit-quick.json
python experiment_manifest.py /path/to/explicit-quick.json /path/to/explicit-deliberate.json
python -m unittest test_experiment_manifest -v
```

The CLI reads UTF-8 JSON, rejects duplicate keys and nonfinite values, prints a
validation count on success (exit 0), and reports invalid input on stderr (exit 2).
It never writes the output path, creates directories, imports a simulator, calls a
model, or changes input files. Paths are interpreted relative to the caller's
working directory, not the manifest directory. Validation does not reserve paths
or check writability/existence; runners must handle output creation safely.

For imports:

```python
from experiment_manifest import validate_manifest, validate_comparison

validate_manifest(explicit_mapping)  # raises ManifestError, a ValueError subclass
validate_comparison([quick_mapping, deliberate_mapping])
```

The API returns the original input unchanged. Comparison requires at least two
individually valid manifests and exact matching controls, including **both** mode
specifications and ordered seed lists. Only `active_mode` and `output_path` may
differ; paths must resolve to distinct destinations. Same-mode replicated plans
are allowed; this is a control-consistency check, not a coverage or results check.
Different difficulty/pressure conditions belong in separately matched comparisons,
not in a comparison which silently changes controls. JSON numeric representations
are compared conservatively (e.g. `1`, `1.0` and `true` do not match).

## Verification commands

Targeted tests are simulator-independent and use temporary synthetic files. For
the full existing suites on the provisioned runtime:

```sh
export PYTHONPATH=/opt/data/research/freeway/source/src:/opt/data/research/freeway/site-packages
export SDL_VIDEODRIVER=dummy
export PYGAME_HIDE_SUPPORT_PROMPT=1
/usr/bin/python3.13 -m unittest discover -v
/usr/bin/python3.13 -m unittest discover -s tests -v
```

The human-review handoff records actual outcomes and commit SHA. These checks do
not run inference or establish model quality, held-out performance, manipulation
validity, or correctness of a future runner's application of these declarations.
