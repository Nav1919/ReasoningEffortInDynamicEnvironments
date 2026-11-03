# Published Freeway pilot evidence

These are historical records from October 8, 2026, not new publication-time trials.
The original local folder is `results/freeway_study_20261008T025226Z/`.

## Contents and transformations

- `diagnostics.jsonl`: all 135 requests and raw responses, reference outcomes,
  errors/validity and timings, across 15 distinct situations and 3 sampling seeds.
- `situations.json.gz`: complete reachable states, action prefixes, hidden timers,
  RNG state and independently simulated reference outcomes.
- `live_*.json.gz`: all 15 complete episodes, including requests, raw responses,
  observations, executed/waiting actions, late responses, timing and summaries.
  Gzip is lossless; JSON formatting was compacted before compression.
- `live_manifest.json`: all episode statuses and runnable per-episode command
  equivalents. Executable/script/output paths were normalized for a fresh clone;
  commands are equivalent recipes, not byte-identical historical shell commands.
- `metadata.json`: recorded Ollama version, installed model digest/settings,
  environment-source hash, difficulty and seed mapping.
- `diagnostic_warmup.json`: diagnostic warm-up; live warm-ups are inside each log.
- `run_source/`: exact historical study/runner/test snapshots, retained as
  provenance, not the supported entry points. Run current root-level scripts.
- `original_sha256.json`: hashes of the original local input bytes, before
  publication transformations. These are provenance identifiers, not checksums
  of the normalized package. `SHA256SUMS` checks the actual packaged files.
- Four CSV/JSON summary pairs (CSV uses portable LF line endings): diagnostic, per-episode, per-interval, and paired.

All personal repository/home path prefixes in published JSON records were replaced
with `<REPO>`/`<USER>`. The manifest uses sibling compressed log names; console-path
references were removed because console output duplicates structured records and
is not included. Raw actions, model prompts/responses, measurements, and statuses
were preserved. Prompts do not contain the replaced filesystem prefixes.
Original logs, before-task backups and consoles remain local and were not deleted.
No models, virtual environment, caches, credentials or bulk console duplicates
are included. The earlier four-state diagnosis's separate local logs are outside
this package; its historical claims are not part of the reproducible tables here.

## Provenance and limits

Historical code parent: `ada9978` (the study runner was uncommitted at collection;
its full source is in `run_source/`, so no clean historical study commit exists).
RealtimeGym: `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b`, installed from the
[SALT-NLP repository](https://github.com/SALT-NLP/RealtimeGym).
Audited Freeway source SHA256:
`9a0a252cb1db44830920268f745f0dadd3a00e4ccbe6863b36a38daa3126367a`.
Local recorded Python setup: 3.13.2 on macOS; full historical OS/hardware state
was not captured. Dependencies are recorded in the root lock file.

Model: `qwen3:4b-q4_K_M`, digest
`2bfd38a7daaf4b1037efe517ccb73d1a3bbd4822cf89f1a82be1569050a114e0`,
Ollama 0.35.1. Live sweep: progress/full, thinking off, temperature 0.6,
model seed 0, context 4096, output limit 2048, 100-turn maximum, default/wait S.
Each exact request is preserved. The diagnostic uses three prompt/board variants
and model sampling seeds 0, 1, 2. No held-out partition was used in this pilot.
All manifest episodes completed; no failed episode is silently omitted. The
summarizer warns about and retains any future incomplete manifest entries, which
are excluded from outcome aggregates. Missing measurements are not fabricated.

## Reproduce without model calls

From the repository root, after installing dependencies:

```sh
python freeway_study.py summarize --output evidence/freeway_20261008
python replay_freeway.py evidence/freeway_20261008/live_01_seed0_tick2.json.gz
python -m unittest test_model_freeway.py test_freeway_study.py test_reproducibility.py
```

The summary command overwrites only derived summaries; it leaves raw records
untouched. Replay checks actions/transitions, not original timing or new outputs.
For a checksum check, run `shasum -a 256 -c SHA256SUMS` inside this directory.

A fresh full inference replication (NOT needed for reproduction above) uses a
new output folder and an already running Ollama server:

```sh
python freeway_study.py all --output results/freeway_replication_01
python freeway_study.py summarize --output results/freeway_replication_01
```

This launches 135 diagnostic calls plus 15 live episodes, takes substantial time,
and was not run during publication. Sampling, caching and scheduling may change
fresh outputs even with fixed seeds. Do not present those future outputs as an
identical reproduction of historical model decisions.
