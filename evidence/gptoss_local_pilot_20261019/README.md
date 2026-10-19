# GPT-OSS local attempts — October 19, 2026

The user authorized the download. GPT-OSS 20B was installed and its Low/Medium/High
controls verified, but **the planned 18-question comparison did not complete**.
There are no usable native-model answers or safety/quality findings here.

| Attempt | Setup load limit | What happened | Game questions |
|---|---:|---|---:|
| 1 | 180 s | No-text model load timed out after 180.081 s; 17 entries remained unrun | 0 |
| 2 | 600 s | Load finished in 109.450 s; first Low answer timed out after 180.133 s; 17 entries remained unrun | 1 attempted, 0 returned |

Medium and High were never queried. The retry loading faster does not establish
that the higher deadline caused success: system load and caches could differ.
Measured-answer settings stayed at 180 seconds and 2048 tokens in both recipes.
Every planned question and all statuses remain in each attempt's saved plan.

Machine: Apple M3, 16 GiB RAM; Ollama 0.35.1. Installed model size:
13,793,441,566 bytes, MXFP4, architecture `gpt-oss`; advertised controls are low,
medium and high. Digest:
`f38aa0c53da5f8c49d08c43a99df24ff53167fe68e24664a7777288e7656fdfe`.
The loaded-model snapshot reported 13,980,433,118 bytes and context 4096.
Swap use was high during loading; no pre-load swap baseline was captured, so it
cannot all be attributed to this model. The model was unloaded after failure;
the weights remain installed. No paid API calls or Ollama upgrade occurred.

## Rebuild the summaries without a model

From the repository root, after installing the README dependencies:

```sh
python -m tarfile --filter data -e evidence/gptoss_local_pilot_20261019/records.tar.gz logs/gptoss_saved_01
python freeway_study.py summarize --output logs/gptoss_saved_01/attempt1
python freeway_study.py summarize --output logs/gptoss_saved_01/attempt2
python -m unittest test_gptoss_saved_evidence.py
```

Use a fresh extraction folder. Each attempt produces `comparison_summary.json`
and `comparison_modes.csv`. `outcomes.csv` is a small overview, not a pooled study.
Zero valid answers from one timeout is not evidence that the chosen action was
unsafe: no answer arrived and no diagnostic action/fallback was executed.
Missing usage remains null with reasons, not fabricated zero tokens.

## Archive contents and provenance

`records.tar.gz` contains both complete plans, status manifests, actual run logs,
saved derived summaries, installation/capability records and relevant diagnostics.
Exact runnable source snapshots match their recorded hashes: attempt 1 used
commit `3f9b919`; attempt 2 used `43c5744`. The initial profile-spelling rejection
is retained in the installation audit; the corrected check used actual metadata.

Personal home-path prefixes were replaced with `<USER>` in JSON/text records;
JSON was compacted. Planned user messages and actual raw provider responses are
otherwise unchanged. `original_sha256.json` identifies the original local input
bytes; `SHA256SUMS` verifies this published package. No models, caches or private
credentials are included. Original local files remain untouched in ignored logs.

Next decision: local setup has not shown practical inference under these limits.
The proposed alternative is the pinned API model in the Step 2 guide, capped at
$1, but that requires explicit user authorization before adding an API adapter.
