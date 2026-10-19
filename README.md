# Reasoning Effort in Dynamic Environments

An LLM can improve a decision by thinking longer, but its observation can become
stale while the world changes. We investigate when an agent should act, think
longer, or look again. Current work is a preliminary Freeway pilot, not an
implemented freshness-aware controller or a validated routing benchmark.

## Install

```sh
git clone https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments.git
cd ReasoningEffortInDynamicEnvironments
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-freeway.txt
```

The exercised setup is macOS, Python **3.13.2**, pygame 2.6.1, and RealtimeGym
revision `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b`.
`requirements-freeway.txt` installs that source revision and the captured
`requirements-lock.txt` package versions. Git and Python are prerequisites.
The lock file is a snapshot of the working environment, not a minimal dependency
list. Installation into a fresh temporary virtual environment on the same Mac,
followed by all 11 tests and offline reproduction commands, passed. Other machines
and operating systems have not been verified.
See [setup](docs/freeway_setup.md) and [interface](docs/freeway_interface.md).

## New reasoning-mode comparisons

For new research runs, follow the [short Step 2 guide](docs/step2_handoff.md).
It saves settings and planned comparisons before model calls, records failures,
and reports missing partners. Existing Qwen off/on stays separate from native
Low/Medium/High. GPT-OSS is installed, but local pilot attempts timed out before
usable answers; the main-model decision remains open.
See the guide for commands, PR review order and the resource decision.

## Start offline

From the repository root, with the virtual environment activated:

```sh
python run_scripted_freeway.py
python freeway_study.py summarize --output evidence/freeway_20261008
python replay_freeway.py evidence/freeway_20261008/live_01_seed0_tick2.json.gz
python -m unittest test_model_freeway.py test_freeway_study.py test_reproducibility.py
```

The baseline always moves up and prints a timestamped `logs/scripted_freeway_*.json`
path. On the pinned setup, seed 0 times out after 100 turns with 25 collisions.
The summary command rebuilds CSV/JSON tables **from saved records**, including
0/5, 2/5, and 2/5 crossings at 1-, 2-, and 4-second intervals. It needs the simulator
for retrospective collision labels, but makes no model calls. Replay executes
saved actions in the simulator and compares every observation, score, collision,
and terminal flag. The example verifies 48 turns and 6 collisions. It does not
recreate the original wall-clock timing or model outputs.

## Smallest model check

Install [Ollama](https://docs.ollama.com/quickstart), open its application (or use
`ollama serve` in a separate terminal), and obtain the exact
[model tag](https://ollama.com/library/qwen3:4b-q4_K_M):

```sh
ollama pull qwen3:4b-q4_K_M
python freeway_study.py smoke --output logs/smoke_01
```

The download is only needed once; it was not performed during publication.
The smoke command sends **one frozen-state request**, saves metadata and the full
response in `logs/smoke_01/smoke.json`, and exits unsuccessfully if it is invalid.
Use a new folder for another attempt. It is a connectivity/action-format check,
not a live episode or evidence of policy quality.

For one live episode (up to about 100 seconds at one second per turn):

```sh
python run_model_freeway.py --prompt progress --board full --thinking off --seed 0 --model-seed 0 --tick-seconds 1
```

The runner prints its `logs/model_freeway_*.json` path. To replay it, pass that
actual filename to `python replay_freeway.py`. No API key or paid service is used.
Avoid concurrent model runs. `python test_local_model.py` is the older arithmetic
connection comparison; it makes two calls, including a potentially slow thinking-on call.

## How the live runner works

Observation → model request in a worker → game ticks continue → strict response
parsing → action at the next tick → JSON log → summary → optional action replay.
This is **asynchronous inference**: traffic moves while the model computes.
Only one request is pending at a time. While waiting the action is **S** (stay),
which can still result in a collision. Each ready action is consumed once.

Defaults: `original` prompt, `full` board, thinking off, 1-second ticks,
environment seed 0, model sampling seed 0, `qwen3:4b-q4_K_M`, temperature 0.6,
4096 context tokens and 2048 generated tokens. `progress` adds crossing guidance;
`structured` removes the text drawing; `progress_source` separately corrects
mechanics wording and was not used in the saved comparison.

A seed is a repeatable initialization choice. Environment seeds 0–4 map to
1000, 1001, 1002, 1003, 1013. The model sampling seed controls sampling separately;
it does not make asynchronous trajectories deterministic. Invalid, truncated,
or failed responses are saved with a null parsed action and an explicit S fallback.
Late responses are retained but cannot act after termination. Warm-up is logged
separately from decision latency. A completed episode is not necessarily a crossing.

## Files and evidence

| File | Purpose and check |
|---|---|
| `run_scripted_freeway.py` | Offline always-up baseline; replay verifies transitions |
| `test_local_model.py` | Two-call arithmetic connection probe; requires Ollama |
| `run_model_freeway.py` | Live model runner; `test_model_freeway.py` checks parsing/prompt isolation |
| `diagnose_freeway.py` | Earlier four-state diagnostic; requires Ollama |
| `freeway_study.py` | Situation generation, one-call smoke, study orchestration and summaries; `test_freeway_study.py` |
| `replay_freeway.py` | Offline saved-action verification; `test_reproducibility.py` |
| `test_reproducibility.py` | All 15 episode replays and relocated summary regeneration |
| `evidence/freeway_20261008/` | Compact published records, metadata, source snapshots and summaries; [inventory](evidence/freeway_20261008/README.md) |
| `docs/freeway_timing_study.md` | Protocol, measured pilot findings and limitations |
| `docs/freeway_diagnosis.md` | Earlier local audit; referenced ignored logs are not all published |
| `docs/weekly-tracker.md` | Planned work and evidence-linked progress |

**Three different operations:** summary regeneration reads saved records; replay
runs saved actions; rerunning inference asks the model for new choices. Neither
offline operation guarantees identical outputs from fresh model calls.
The saved pilot has 135 fixed-state responses and 15 live episodes. It is small,
has no held-out validation, and does not establish a controller improvement.
Slower ticks change both elapsed time and timing information in the prompt.
Prompt mechanics are simplified, and the model often fails even on frozen states.
No tutorial notebooks or completed final report are included.

PR #5 proposes a separate offline schema with split/mode validation. Integration
is deferred: these historical pilot logs predate that schema and were not collected
with its proposed held-out protocol. This PR does not adopt or merge that work.

## Each Code File

Every new code file must:

- Start with a descriptive header explaining its overview, how to run or import it, inputs/outputs, how it was tested, and links to its unit tests.
- Place descriptive paragraph comments before major, non-obvious code sections explaining their purpose and reasoning.
- Use clear names and self-documenting code where appropriate; comments should explain intent rather than repeat the syntax.
- Be organized, loosely coupled, extensible, and portable across supported systems.
- Have relevant unit tests and validation evidence before the associated pull request is merged.
- Trigger an update to **How to Navigate this Repo** when it is added, moved, or changed in purpose.

## Links to Major Docs & Presentations

| Deliverable | GitHub planning page | External workspace |
|---|---|---|
| Proposal presentation | [Proposal](docs/proposal-presentation.md) | 
| Paper presentation | [Paper](docs/paper-presentation.md) |  https://www.overleaf.com/6226662223swsgskgksdyy#062edd |
| Midterm presentation | [Midterm](docs/midterm-presentation.md) |
| Final presentation | [Final](docs/final-presentation.md) | 
| Final report | [Final Report](docs/final-report.md) |


## Related Works

Use [Related Works](docs/related-works.md) to track each paper by **paper name, summary, and annotated paper or notes**. Entries will be added as the literature review progresses.

## Team

| Member | Role |
|---|---|
| Pranav Panicker | Project member |
| Shohini Rhea Sarkar | Project member |
| Akash Wudali | Project member |
