# Reasoning Effort in Dynamic Environments

> Freshness-aware test-time compute for LLM agents in changing environments

## Project Intro

An LLM agent can improve a decision by thinking longer, but the environment may change while it reasons. This project investigates **when more reasoning is worth its cost and when waiting makes an observation stale**.

Our research question is: **How should an LLM agent allocate reasoning effort when the environment can change during inference?** We plan to compare fixed-compute and difficulty-aware approaches with a freshness-aware policy that can act now, think longer, or refresh its observation before acting. Evaluation will consider decision quality, latency or compute, and performance under different rates of environmental change. The benchmarks and implementation are still being selected.

## How to Navigate this Repo

The repository contains the research plan and an agent automation setup. Research experiment code and tutorial notebooks have not been added yet.

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
| `docs/automation.md` | Hermes/Codex setup, credential boundaries, budgets, validation and remaining actions | Available |
| `automation/manage.py` | Host-only identity verification, disk/Docker preflight, isolated runtime preparation and draft PR publishing; run `python automation/manage.py --help`; tested by `tests/test_automation.py` | Available |
| `automation/` | Native Hermes profiles, Codex sandbox configuration, two-container deployment and research task templates | Available; runtime validation pending |
| `tests/test_automation.py` | Offline automation checks; run `python -m unittest discover -s tests -v` | Available |
| `automation/sandbox_smoke.py` | No-model container test of workspace writes and denied home/Git/network access; run using the mount command in `docs/automation.md`; failure propagation tested by `tests/test_automation.py` | Passed with approved one-off worker profile |
| `automation/security-proposal/` | Pinned OpenAI syscall profile and inactive worker override requiring explicit security approval | One-off test approved and passed; persistent activation pending |
| `automation/seed_linux_state.py` | Seed dedicated Windows runtime into Linux-owned Docker volumes; run after preparation; manual ownership and integration checks in `docs/automation.md` | Available |
| `automation/configure_worker.py` | Post-migration callback routing and approved board-read permissions; mounted run in `docs/automation.md`; tests in `tests/test_automation.py` | Available |
| `automation/export_worker.py` | Export a clean Linux-volume agent branch through a read-only, offline Git-bundle helper; run with `--branch agent/task-id --worktree /workspace/path`; real bundle tests in `tests/test_automation.py` | Available |
| `automation/board_snapshot.py` | Stable read-only board JSON for Hermes monitor-script hashing; copy to controller scripts as documented; tests in `tests/test_automation.py` | Available |
| Research code and notebooks | Add paths and descriptions as they are created | Not yet available |

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
