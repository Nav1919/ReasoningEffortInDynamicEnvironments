# Research contributions

Read README.md and docs/weekly-tracker.md before work. Keep changes within the assigned research task.

Each research task should state its hypothesis, dependencies, acceptance checks, artifacts, seed/config manifest, compute allowance and stop condition. Never fabricate results, mark missing runs successful, tune on held-out starts or silently change the frozen model. Preserve failed runs and negative findings.

Use an isolated agent branch/worktree for agent-assisted changes. Run relevant research tests and record actual commands/results, including failures and checks not run. Make meaningful commits after tested milestones. Use the verified human-approved author identity and disclose agent assistance truthfully; author identity is separate from authentication, pusher and signing.

Leave a human-review handoff with commit SHA, changed paths, checks, artifacts, usage/cost and remaining uncertainty. Never self-approve, merge, force-push, rewrite shared history, bypass branch protection or change repository security. Block for missing scientific decisions, credentials or approved compute budget.

Orchestration, deployment, platform credentials, agent-home configuration and infrastructure diagnostics are maintained outside this repository. Do not add them to research changes. Keep reusable research code, experiment configuration, tests and reproducibility documentation here.
