# Merged Freeway baseline: offline reproducibility gate

Date: October 30, 2026. Prepared with Hermes/Codex assistance; pending human
review. Baseline: `22cdee9a08bdfbbfc1059a22f0a230a5fc02e05c`, assigned isolated
branch `agent/weekend-reproducibility-20261030`. Initial worktree was clean.
Configured author Pranav Panicker (GitHub noreply identity) matched the owner-authored
merged history; no identity configuration was changed. Authentication, pushing
and signing were not exercised.

## Scope and stop condition

**Hypothesis:** the merged baseline can be independently checked offline with the
provisioned pinned simulator, without changing scientific choices.
**Dependencies:** baseline above, `/usr/bin/python3.13`, selected RealtimeGym
source revision `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b`, NumPy and pygame below.
**Acceptance:** both existing suites pass without skips, all saved evidence hashes
and 15 replays pass, independent smoke matches the original, and provenance is
recorded. **Compute allowance:** local offline checks only, within the card's
1,200 seconds; no installs, downloads, network, model inference or paid experiments.
**Stop:** tested documentation/evidence commit for human review; block on an
unresolved prerequisite or scientific decision. No new scientific choices were needed.

**Seed/config manifest:** the unchanged
[`live_manifest.json`](../../evidence/freeway_20261008/live_manifest.json) supplies
the 15 historical episodes; their requested seeds 0–4 map to
1000/1001/1002/1003/1013, with historical 1/2/4-second intervals. Replay executes
saved actions, not those wall-clock intervals. Smoke uses Freeway-v0, difficulty E,
input seed 0 / mapped seed 1000, `USUSUSUSUS`, maximum ten steps, no rendering.
Original smoke configuration/provenance remains in
[`manifest.json`](../../artifacts/freeway/manifest.json).

## Runtime provenance

This is **not a fresh full-package installation**. It is the provisioned,
unmodified selected-source headless Freeway path. No dependencies were installed.
The full macOS lock file and its fresh-install claim were not revalidated here.

| Component | Observed value |
|---|---|
| Interpreter | `/usr/bin/python3.13`, CPython 3.13.5, GCC 14.2.0 |
| Platform | Linux 6.18.54.1-microsoft-standard-WSL2, x86_64, glibc 2.41 |
| RealtimeGym | 0.1.0, imported from `/opt/data/research/freeway/source/src/realtimegym/__init__.py` |
| NumPy | 2.2.6, `/opt/data/research/freeway/site-packages/numpy/__init__.py` |
| pygame | 2.6.1, `/opt/data/research/freeway/site-packages/pygame/__init__.py` |

The external `/opt/data/research/freeway/manifest.json` equals the historical smoke
manifest's `source_provenance`. All ten listed selected-source/support files and
both cached wheel archives match their recorded SHA-256 values.
[Full actual/expected hashes and module paths](validation/provenance.json) are
retained. Hash agreement establishes consistency with provisioned records, not
an independent online authentication of upstream; no upstream checkout/fetch was done.
Wheel hashes do not constitute an audit of every extracted site-packages file.

## Exact execution commands and results

Run from repository root; the output directory below was newly created.
For another run use a new directory and change the inline comparison path too;
the smoke CLI deliberately refuses to overwrite evidence.

```sh
export PYTHONPATH=/opt/data/research/freeway/source/src:/opt/data/research/freeway/site-packages
export SDL_VIDEODRIVER=dummy
export PYGAME_HIDE_SUPPORT_PROMPT=1
mkdir -p docs/weekend/validation
/usr/bin/python3.13 -m unittest discover -v > docs/weekend/validation/baseline-tests.txt 2>&1
/usr/bin/python3.13 -m unittest discover -s tests -v > docs/weekend/validation/smoke-tests.txt 2>&1
/usr/bin/python3.13 scripts/freeway_smoke.py --output docs/weekend/validation/smoke-repeat.jsonl > docs/weekend/validation/smoke-cli.txt 2>&1
```

Each command exited 0. Initial uncaptured checks also passed: 14 tests in 4.322s,
7 in 0.666s. The retained second execution produced:

| Check | Actual result / artifact |
|---|---|
| Root suite | 14 passed, 4.219s; [log](validation/baseline-tests.txt) |
| Smoke suite | 7 passed, 0.676s; [log](validation/smoke-tests.txt) |
| Independent explicit CLI | ten steps, reward 90, done false, `max_steps`; [stdout](validation/smoke-cli.txt), [raw records](validation/smoke-repeat.jsonl) |
| Saved evidence | all 33 SHA256SUMS entries match |
| Saved live replays | all 15 manifest episodes replay every transition successfully |
| Relocated summaries | four JSON/CSV table pairs regenerated exactly; 135 diagnostic records, 15 situations; crossings 0/5, 2/5, 2/5 |
| Independent smoke equality | all 13 parsed records equal original, including raw observations and provenance; byte hashes also equal |

The new smoke and original sample both hash to
`15322560bbc35c29735c3d2b4a0cdd385dbb127c18d57b9c550f654a94089382`.
The smoke suite itself launches another independent CLI subprocess. Across both
suite executions plus the explicit CLI there were three ten-step real smoke
processes, not three new model episodes.

The following exact inline audit command generated `provenance.json` (exit 0):

```sh
/usr/bin/python3.13 - <<'PY' > docs/weekend/validation/provenance.json
import hashlib
import json
import platform
import sys
from pathlib import Path
import numpy
import pygame
import realtimegym
base = Path('/opt/data/research/freeway')
manifest = json.loads((base / 'manifest.json').read_text())
historical = json.loads(Path('artifacts/freeway/manifest.json').read_text())
checks = {}
for group, folder in [('source_files', 'source'), ('wheels', 'wheels')]:
    checks[group] = {}
    for name, expected in manifest[group].items():
        actual = hashlib.sha256((base / folder / name).read_bytes()).hexdigest()
        checks[group][name] = dict(expected=expected, actual=actual, matches=actual == expected)
        assert actual == expected, name
assert manifest == historical['source_provenance']
sample = Path(historical['sample']['path'])
assert hashlib.sha256(sample.read_bytes()).hexdigest() == historical['sample']['sha256']
repeat = Path('docs/weekend/validation/smoke-repeat.jsonl')
assert [json.loads(line) for line in sample.read_text().splitlines()] == [json.loads(line) for line in repeat.read_text().splitlines()]
entries = Path('evidence/freeway_20261008/SHA256SUMS').read_text().splitlines()
for entry in entries:
    expected, name = entry.split(maxsplit=1)
    assert hashlib.sha256((Path('evidence/freeway_20261008') / name).read_bytes()).hexdigest() == expected, name
print(json.dumps(dict(executable=sys.executable, python=sys.version, platform=platform.platform(), machine=platform.machine(), modules={m.__name__: dict(version=m.__version__, file=m.__file__) for m in (numpy, pygame, realtimegym)}, source_revision=manifest['source_commit'], scope=manifest['scope'], checks=checks, external_manifest_matches_historical=True, evidence_checksums_verified=len(entries), sample_sha256=historical['sample']['sha256'], repeat_sha256=hashlib.sha256(repeat.read_bytes()).hexdigest(), independent_sample_equal=True), indent=2))
PY
```

This inline audit is documentation, not a new supported executable. Existing
regression coverage is in [evidence integrity](../../test_evidence_integrity.py),
[reproducibility](../../test_reproducibility.py) and
[smoke tests](../../tests/test_freeway_smoke.py). These include deliberate corrupted
start/transition/summary rejection, failed-run retention, invalid settings, source
hash and mapped-seed rejection, action exhaustion, collision/terminal semantics,
snapshot preservation and mutated-record oracles. No concrete defect was found;
no implementation or regression tests needed modification. No commands failed,
no skips occurred, and no original evidence, golden samples or historical
manifests were rewritten. Summary tests operate on temporary copies.

## Review handoff and limits

Changes are this report, its validation artifacts and one README navigation link.
No scientific model, experiment settings, evaluation protocol, roadmap, simulator
or infrastructure changed. The commit SHA is supplied in the task's review
handoff (avoiding a self-referential commit identifier here).

Not run: full-package installation, rendering, other Python/dependency versions,
fresh inference, original asynchronous wall-clock timing, fresh model-quality or
held-out evaluation, new pressure/difficulty experiments, or independent teammate
setup. The unchanged upstream example was hash-checked, not executed in this task.
The known headless ten-step smoke equality depends on matching Python patch and
dependency versions because versions are included in the golden metadata.
This is evidence of offline consistency, not controller improvement or scientific
generalization. Historical provenance and prior limitations remain applicable.

Usage: one coding worker, local CPU checks, zero inference/API/paid experiment
calls. Coding-assistant subscription tokens/cost are unavailable; no estimate is
asserted. Human review remains required. Nothing was pushed or merged; GitHub
publishing is a separate host step.
