# Reproduce Freeway's supplied example without an LLM

Owner: coder (Pranav's agent-assisted work; other team tasks remain unassigned).
Hypothesis: the upstream example exposes U/D/S and reproducible game transitions.
Dependencies: approved RealtimeGym source revision and install requirements.
Scope: inspect the example, document installation, run a small deterministic
smoke example, retain raw observation/action/outcome records. No paid inference.
Acceptance: a teammate can rerun documented commands; meaningful tests cover
the interface; record whether seeds actually reproduce trajectories.
Artifacts: install guide, source revision, commands, seed/config manifest, raw
logs, test output, limitations. Update README navigation.
Budget: one worker, 20 minutes, one attempt, zero paid experiment API calls.
Stop: missing runtime/network permission, ambiguous API, exhausted budget, or
first complete tested milestone. Block with one concrete question when needed.
Workflow: preserved worktree and agent branch; tested milestone commits; human
review handoff. Keep the card local-only until host publishing and GitHub checks
can be independently verified. Never merge.
