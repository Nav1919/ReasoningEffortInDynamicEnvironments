# Research agents

Hermes owns task state, scheduling, retry limits, and Discord delivery. Use its
native Kanban tools; do not build another scheduler or dispatcher.

Read the assigned card and `docs/weekly-tracker.md`. Only implement its stated
scope. Each research card must specify a hypothesis, dependencies, acceptance
checks, artifacts, seed/config manifest, compute allowance, and stop condition.
Never fabricate results, mark missing runs successful, tune on held-out starts,
or silently change the frozen model. Keep failed runs and negative findings.

Use one `agent/<task-id>` branch and a preserved Git worktree per coding card.
Before edits, check the current branch and status. Never work on main, merge,
force-push, rewrite shared history, or change repository security settings.
Make a meaningful commit after each tested milestone, not empty/time-based
commits. Verify author name/email against the host's verified identity record;
stop if missing. Authorship is the user's requested identity; describe Hermes
and Codex assistance truthfully in PRs and task logs.

Run relevant tests and record commands/results. Follow README code headers and
navigation requirements. Leave artifacts plus a review handoff, including commit
SHA, changed paths, checks, costs/usage, remaining uncertainty, and PR URL when
available. Workers have no GitHub publishing credential: request host publishing.
Call `kanban_request_review` for a human review; never self-approve. The human
merges through GitHub after required checks. Block for missing credentials,
budget, scientific decisions, or security changes. Do not repeatedly retry a
blocked task. Use heartbeat/comments for milestones; Hermes delivers concise
Discord progress and HITL questions. Never put credentials in cards or logs.
