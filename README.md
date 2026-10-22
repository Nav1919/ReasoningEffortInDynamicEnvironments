# Reasoning Effort in Dynamic Environments

> Freshness-aware test-time compute for LLM agents in changing environments

## Project Intro

An LLM agent can improve a decision by thinking longer, but the environment may change while it reasons. This project investigates **when more reasoning is worth its cost and when waiting makes an observation stale**.

Our research question is: **How should an LLM agent allocate reasoning effort when the environment can change during inference?** We plan to compare fixed-compute and difficulty-aware approaches with a freshness-aware policy that can act now, think longer, or refresh its observation before acting. Evaluation will consider decision quality, latency or compute, and performance under different rates of environmental change. The benchmarks and implementation are still being selected.

## How to Navigate this Repo

The repository contains planning pages and a verified no-LLM Freeway smoke runner. No tutorial notebooks or LLM evaluation runner have been added yet.

| Path | What it contains | Status |
|---|---|---|
| `README.md` | Project introduction, navigation, usage, standards, and links | Available |
| `docs/proposal-presentation.md` | Proposal checklist | Available |
| `docs/paper-presentation.md` | Paper-presentation planning page | Available |
| `docs/midterm-presentation.md` | Midterm checklist | Available |
| `docs/final-presentation.md` | Final-presentation checklist and code-unit/test inventory | Available |
| `docs/final-report.md` | Final-report working outline | Available |
| `docs/related-works.md` | Paper summaries and annotation links | Available |
| `docs/weekly-tracker.md` | 11-week task plan, check-ins, and result log | Available |
| `scripts/freeway_smoke.py` | Bounded fixed-action JSONL runner; usage: `python scripts/freeway_smoke.py --output NEW.jsonl` with the [pinned setup](docs/freeway-setup.md); tested by `tests/test_freeway_smoke.py` | Verified, pending review |
| `tests/test_freeway_smoke.py` | Settings/API unit checks and real subprocess replay; run `python -m unittest discover -s tests -v` with the pinned setup | 7 tests passed |
| `docs/freeway-setup.md` | Tested headless commands, runnable-file/API details, provenance, limits and assistance disclosure | Available |
| `requirements-freeway.txt` | Minimal selected-source runtime pins (not full upstream installation) | Available |
| `artifacts/freeway/` | Actual ten-step JSONL sample and verification/provenance manifest | Available |

@Team Members: When adding code, list **each runnable code file** here with its purpose, usage, and unit-test link. Keep notebook entries here too, including prerequisites and the order in which to run them.

## How to Export & Use the Code

To obtain the current repository:

```bash
git clone https://github.com/shohinirheasarkar/ReasoningEffortInDynamicEnvironments.git
cd ReasoningEffortInDynamicEnvironments
```

You can also select **Code → Download ZIP** on GitHub. 

## Tutorial Notebooks

No tutorial notebooks have been added yet. 

## Each Code File

Every new code file must:

- Start with a descriptive header explaining its overview, how to run or import it, inputs/outputs, how it was tested, and links to its unit tests.
- Place descriptive paragraph comments before major, non-obvious code sections explaining their purpose and reasoning.
- Use clear names and self-documenting code where appropriate; comments should explain intent rather than repeat the syntax.
- Be organized, loosely coupled, extensible, and portable across supported systems.
- Have relevant unit tests and validation evidence before the associated pull request is merged.
- Trigger an update to **How to Navigate this Repo** when it is added, moved, or changed in purpose.

## Progress Trackers

- [Weekly project tracker](docs/weekly-tracker.md): 11-week plan, Monday check-ins, Tuesday/Thursday deliverables, and weekly result log.
- [GitHub Issues](https://github.com/shohinirheasarkar/ReasoningEffortInDynamicEnvironments/issues): concrete tasks, assignments, discussions, and bugs.
- [Pull Requests](https://github.com/shohinirheasarkar/ReasoningEffortInDynamicEnvironments/pulls): code changes, review, and linked tests.
- [GitHub Projects](https://github.com/shohinirheasarkar/ReasoningEffortInDynamicEnvironments/projects): team board

Suggested workflow: create an Issue → assign an owner → work on a branch → open a PR with `Closes #issue-number` → review tests and documentation → merge and mark complete.

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
