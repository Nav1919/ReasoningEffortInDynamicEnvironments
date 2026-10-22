# Worker persistence compatibility proposal

Status: disposable tests approved and completed. Not installed in either persistent service; no credentialed coding retry was run.

Pinned upstream: NousResearch/hermes-agent `4e58c721c8cf9b51c46636ea84ea6a5cb540880a`.
Patch: `worker-persistence.patch` in this directory.

## Verified failure

The real failed coding worker saved 37 receipts; sequence 38 retained a `session.sidecars` / `_usage_anchor` write. A credential-free native managed-worker test reproduced `permission_denied`. Trace-only instrumentation (no changed checks) located the rejection at `gateway/session_worker.py:_claim`, line 37: the live process birth differed from the supplied birth by exactly -1.0 seconds. The installed psutil 7.2.2 Linux implementation adds the current `/proc/stat` boot epoch to immutable kernel start ticks. Clock corrections can change that epoch. One repeat passed, consistent with a timing-dependent failure; this is not a stable successful handoff.

Separately, `agent/codex_runtime.py` writes `codex_thread_id` through `patch_session_model_config`, but the worker sidecar allowlist omits it. A fake-Codex test exposed `invalid_params`; pure-function validation confirms this field is refused by the original handler.

## Proposed changes and limits

1. Extend the existing macOS kernel-start-time path in `process_birth` to Linux. Continue exact equality, live-process, same-user, parent/descendant, session, generation, epoch and secret checks. Do not add a tolerance or bypass. Windows behavior stays unchanged. This changes the representation of Linux spawn identities throughout the patched worker install, so never mix old running processes or attempt to adopt retained pre-patch journals. Start from fresh disposable state for the first test; inspect global spawn/reaper callers before any persistent rollout.
2. Add only `codex_thread_id` to allowed worker sidecars, accepting null or a nonempty string of at most 256 characters. The existing assigned-session receipt remains mandatory. Unknown fields remain rejected. This is an explicit small expansion of worker persistence authority.

Three extracted-function tests pass: simulated Linux clock correction fails the old identity but preserves the candidate identity; Windows identity is unchanged; original thread-ID refusal is reproduced and candidate type/length/unknown-key checks pass. These tests use fake process/database objects. They are not evidence that a patched managed runtime works.

## Requested first test

Use a disposable nonroot container, no credentials, no external network, no production volumes, unchanged Docker restrictions, and fresh temporary Hermes state. Apply the patch only there. Run the native managed-worker fake-model test and a fake-Codex persistence test, checking durable transcript, thread ID, usage and worker retirement. Preserve negative authorization tests. Stop on failure, with no research task retry and no persistent activation. The existing controller remains on the unmodified image.

The failed research card and original outbox remain preserved and blocked. No model-funded coding retry, publishing handoff or deployment is claimed.

## Original source checksums

- process_identity: `0635c722fbfed680fd62aedcaafc5d87c534614f63f17c472ac78195ea3f2f50`
- worker_context: `c6e624108a97dc1a094374dee4947af8c6f9e7763a81a3d4ed212b660560277f`

## Approved disposable results

The operator approved credential-free patched-runtime testing. The unmodified native managed-worker history/tool test passed (14.60 s). A second suite passed 11 checks (17.01 s): two fake-Codex cases with durable thread ID, transcript and 10/5 token counts; native receipt sequencing, wrong-session/wrong-generation/adoption and context/identity guards; and native late-result fencing. The fencing test's synthetic greeting was updated to the kernel-start identity representation; no rejection assertion was removed. An initial run rejected its legacy epoch greeting as expected until that fixture was aligned.

Exact fixture/test changes are preserved in `worker-persistence-tests.patch`. These are deliberately fake model/transport tests, not evidence that actual Codex tools, sandbox, commits or a review handoff passed. Both patched source files were mounted read-only into fresh disposable containers: nonroot UID 10000, no capabilities, no-new-privileges, read-only root, temporary state, network none and no production home volumes or credentials. The production controller remains unchanged.

## Proposed next bounded credentialed validation

With separate explicit approval, create one new native Kanban validation card (preserve the old failed card blocked), one attempt and 180 seconds. Use only the existing dedicated worker login, the previously tested worker-only seccomp and six scoped callback permissions, plus this tested compatibility patch in that one container. Ask Codex to add only `docs/persistence-validation.md`, run existing offline checks, make a verified-user local commit, comment and request human review. No external GitHub credential, push, merge, experiment, new login or persistent activation. Restore the worker's prior Codex policy in `finally`; record and stop on failure. This uses subscription model allowance; turn/time limits are not a provider-enforced dollar cap. Export/publishing remains the separate host boundary.

## Approved real validation and newly diagnosed routing defect

The operator approved one real attempt using only the dedicated worker login. New card `t_261eb224`, branch `agent/persistence-validation`, preserved worktree `/workspace/repo/.worktrees/t_261eb224`, ran once and blocked at its first terminal approval. It sent a heartbeat and recorded its blocker natively; no files or commits changed. The original worker policy was restored and the test container stopped. The old failed card remains blocked.

Nonsecret configuration inspection confirms the coder profile selected `openai_runtime=codex_app_server`, but its durable session has no Codex thread ID. Native `agent/managed_worker.py:_construct_agent` passes no `api_mode`; AIAgent consequently infers `codex_responses` from provider `openai-codex`. The managed constructor loses the configured app-server selection. `worker-runtime-routing.patch` preserves the frozen profile selection using Hermes's existing runtime selector. Three fake-factory tests pass for explicit OpenAI/Codex app-server mode and unchanged auto mode. No live routing patch was applied.

The worker template also used root `toolsets`, whereas native launch policy selects `platform_toolsets.cli`. The template now explicitly selects only Kanban there. A future test must temporarily apply this tighter profile routing, then restore it along with the Codex policy. The correction removes the unsandboxed Hermes terminal path from the offered tools; it does not approve it. Actual coding should occur through Codex's own workspace sandbox. Another bounded real attempt requires explicit authorization because the approved single attempt was consumed.

Native `_resolve_toolsets` with the tightened worker template returned exactly `{kanban}` in an offline disposable probe. The repository now passes 29 offline checks, including the explicit worker-surface constraint. Routing factory regressions are preserved in `worker-runtime-routing-tests.patch`.
