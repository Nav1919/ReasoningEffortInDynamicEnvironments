# Hermes + Codex research automation

## Implementation and boundaries

Hermes supplies the durable Kanban board, cron, Discord adapter, subscriptions,
retry breaker and dispatcher. Codex runs coding turns through Hermes' native
`codex_app_server` runtime. There is no custom orchestration service.

Two containers on **one host** share `.runtime/board`. The controller gets its
own provider/Discord credentials and no source checkout. Its toolsets permit
Kanban and cron only. The worker gets a separate Hermes home, dedicated Codex
login, board mount and isolated repository clone; it gets no controller home,
Discord token, GitHub token, personal plugins, host home or Docker socket.
Only `coder` can be claimed by the worker dispatcher. Both homes must use the
same absolute board/workspace paths. This is single-host SQLite, not a fleet.

The worker uses the existing standalone native dispatcher with `--force` because
it intentionally has no messaging gateway. Upstream deprecates this command but
retains that escape hatch for hosts without a gateway. The controller's
dispatcher is disabled, so two dispatchers do not race. Human review dispatch
is disabled in both homes. Shared board contents are trusted coordination data;
containers do not defend the board against malicious workers modifying it.

Codex workspace sandboxing disables shell network access. The outer container
has network access for model requests. This is **not an egress allowlist**;
model credentials remain accessible within the worker container. Git worktrees
share the worker clone's Git metadata and are not independent security domains.
One worker at a time bounds contention. No privileged mode, host networking,
or sandbox bypass is configured. If the nested sandbox is unavailable, stop
and resolve that explicitly; do not enable full access automatically.

## Versions and sources

Source inspected: Hermes commit
`4e58c721c8cf9b51c46636ea84ea6a5cb540880a` (October 21, 2026).
The build uses its unmodified Dockerfile and locked upstream installation.
Codex npm release `0.163.0` was verified in the official npm registry.
Base images are tagged upstream versions; record resulting image digests before
production use. This is not a fully reproducible supply-chain lock.

- [Native Codex runtime](https://github.com/NousResearch/hermes-agent/blob/4e58c721c8cf9b51c46636ea84ea6a5cb540880a/website/docs/user-guide/features/codex-app-server-runtime.md)
- [Kanban and shared homes](https://github.com/NousResearch/hermes-agent/blob/4e58c721c8cf9b51c46636ea84ea6a5cb540880a/website/docs/user-guide/features/kanban.md)
- [Discord setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/discord)
- [Cron](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [GitHub noreply attribution](https://docs.github.com/en/account-and-profile/reference/email-addresses-reference)

## Commit authorship and publishing

The existing host Git credential authenticated as **Nav1919**, account ID
**75394407**, profile name **Pranav Panicker**, with push access. The supplied
repository URL redirects to **Nav1919/ReasoningEffortInDynamicEnvironments**.
The personal-email verification endpoint was unavailable (404), so the setup
uses the documented account-ID noreply address:
`75394407+Nav1919@users.noreply.github.com`. It does not claim the previous
local Gmail address is verified. No global Git identity is changed.

```bash
python automation/manage.py identity --login Nav1919
```

The command verifies the authenticated account before setting local `user.name`,
`user.email` and `user.useConfigOnly`. An explicit personal `--email` must appear
as verified in `/user/emails`; otherwise the command refuses it. The private
local identity record is excluded from Git. Do not hand this host credential
to the workers: it currently has admin access and is broader than needed for
unattended publishing. A future restricted publisher credential needs only
repository Contents/PR write and metadata/check read, never administration.

After relevant tests pass and meaningful milestone commits exist:

```bash
python automation/manage.py publish --branch agent/task-id --title "Concrete change" --body-file review.md --source .runtime/repo
```

Use the actual worktree path for `--source` when publishing a worktree. The host
refuses main, dirty checkouts, wrong current branches and new commits with a
different author. It pushes only the explicit agent ref, opens/reuses a draft
PR, and queries GitHub's commit objects to verify account association. Review
the PR evidence; publishing does not independently prove scientific correctness
or tests. Never put tokens in the body file. Keep that file outside the source
checkout or commit it before publishing, so the cleanliness check can pass.

Commit **author identity**, authentication/**pusher identity**, signature status
and agent provenance are separate. User author association does not imply a
cryptographically Verified signature or a human-only implementation. Commit
messages/PR descriptions disclose agent assistance. Branch commits may not count
on the contribution graph until human merge to the default branch.

An active `Protect main` ruleset was observed through GitHub's read API. Effective
rules require one approving review, dismissal of stale approvals, resolved
review threads, and protection against deletion/force-push. No required status
check context was returned. Classic branch protection returned 404; no protection
settings were changed. The CI workflow adds tests; making `automation-tests`
mandatory is a separate owner-approved security change. Until then the human
reviewer must check its result before merging.

## Prepare and build

Requires Git, Python 3.11+, Docker Linux containers and sufficient disk/memory.
Run from the repository root. Preparation refuses to overwrite an existing
runtime. It copies **no credentials** and starts no services.

```bash
python automation/manage.py prepare
python automation/manage.py preflight
docker build -t hermes-research-base:4e58c721 'https://github.com/NousResearch/hermes-agent.git#4e58c721c8cf9b51c46636ea84ea6a5cb540880a'
docker compose -f automation/compose.yaml build worker
docker compose -f automation/compose.yaml config --quiet
```

The explicit image entrypoint bypasses upstream s6 initialization to run as UID
10000 with capabilities dropped. On Linux, make **only this repository's
`.runtime` directory** owned by UID/GID 10000 before these container commands.
Windows Docker Desktop bind mounts handle ownership differently. Do not mount
the original checkout or personal home as a shortcut.

## Connect credentials inside the dedicated homes

Do not paste secrets into chat, Git, templates or task logs. No Discord token or
controller inference credential was found/configured during implementation.
Existing desktop Codex login is not copied and does not authenticate containers.

```bash
docker compose -f automation/compose.yaml run --rm controller setup
docker compose -f automation/compose.yaml run --rm controller gateway setup
docker compose -f automation/compose.yaml run --rm --entrypoint /usr/local/bin/codex worker login --device-auth
```

Configure the controller's selected
model/provider through the setup wizard, without changing the worker's frozen
research model (research model selection remains a separate scientific decision).
Discord setup must set `DISCORD_ALLOWED_USERS` to your numeric Discord ID;
enable the documented Message Content/Server Members intents, invite to the
intended server/channel and verify only the authorized user can issue commands.
The wizard stores secrets in the controller home, outside Git.

Initialize the board before the worker, then enable the native runtime in a
**coder-profile interactive session**, not in the desktop's personal config:

```bash
docker compose -f automation/compose.yaml run --rm controller kanban boards create research --default-workdir /workspace/repo
docker compose -f automation/compose.yaml run --rm worker -p coder
# Inside this dedicated Hermes session:
# /model (select an available OpenAI Codex coding model)
# /codex-runtime codex_app_server
```

That native command registers Hermes' callback MCP server in the dedicated
Codex home, enabling Kanban handoffs. Merely setting the YAML runtime field
does not perform this registration. Review its generated config; retain
workspace-write and disabled shell network. Test the actual sandbox before
launching a coding card. Do not copy personal plugins/MCP servers.

The native noninteractive equivalent for registration (without toggling the
already configured runtime) is also available:

```bash
docker compose -f automation/compose.yaml run --rm worker -p coder codex-runtime migrate --dry-run --json
docker compose -f automation/compose.yaml run --rm worker -p coder codex-runtime migrate --json
```

## Smoke check, research cards and Discord

```bash
docker compose -f automation/compose.yaml run --rm worker -p coder chat -q "Report current workspace and call kanban_show. Do not edit files or call paid experiment APIs."
docker compose -f automation/compose.yaml up -d controller worker
docker compose -f automation/compose.yaml logs --tail 100 controller worker
```

Then create a card **from the authorized Discord conversation** so Hermes
auto-subscribes its origin thread. Supply `automation/research-task.md` and tell
the controller to use `coder`, a preserved worktree, a unique agent branch,
`max_runtime=1200`, one attempt, and a local-only completion contract. Confirm
the card's paths, runtime, assignee and scope before promoting it. Local-only
is deliberate: workers cannot run GitHub acceptance checks without credentials.
Use human review, host publishing and GitHub CI as distinct evidence gates.

The first coding card should confirm a tiny file edit, meaningful test and
commit, then enter human review. Verify its author on GitHub after host publish.
Use research cards only after the setup PR has been reviewed and the operator
has selected the approved base revision; preparation clones the current branch.
Create worktrees inside the Linux container so their Git metadata uses container
paths, rather than Windows host paths.
For the research card, record the hypothesis, dependency versions, seed/config,
data paths, expected artifacts and experiment allowance. Do not blindly assign
all unchecked weekly tasks or assume calendar dates imply completed research.

Ask the controller in Discord to create one native **hourly cron** check of
existing approved cards. It should report only a meaningful change, failure or
needed decision and should never auto-unblock or create new research work.
Inspect `hermes cron list` in the controller container to confirm destination,
schedule, profile and bounded prompt. Cron management in an actual authorized
chat ensures Discord delivery targets are resolved instead of inventing IDs.

Verify: received progress, review request and one HITL reply; a reply updates
the intended card; restart both containers and confirm durable cards/logs;
leave a blocked card unchanged across cron ticks. No successful delivery or
persistent deployment is claimed until these checks pass.

## Budgets, stop and recovery

Native limits: one active worker, 40 worker turns, 1200-second run budget,
one failed attempt, 2 CPU/4 GiB memory/256 PIDs for worker. **Each card must
also set `--max-runtime 1200 --max-retries 1`** for dispatcher enforcement.
The native runtime may enforce turn budgets differently; the dispatcher is the
outer wall-clock boundary. Controller runs have 20 turns/300 seconds.

These are compute controls, **not a hard daily dollar cap**. Subscription
limits do not guarantee dollar accounting; auxiliary Hermes calls may use its
provider separately. No paid experiments are authorized by this setup.
Before paid work, set a provider-enforced project allowance, scoped experiment
credential and approved run manifest. Review usage daily; do not rely on a
prompt or estimated token price as a spending firewall. Never reuse the
controller's credential in experiments. A dedicated experiment execution
container and billing gate remain required before unattended paid experiments.

Emergency stop without deleting state:

```bash
docker compose -f automation/compose.yaml stop worker controller
```

`hermes pause` stops new work, but is not a guaranteed kill of active jobs and
each separate home may need pausing. Compose stop terminates both service trees.
Inspect retained worktree/commits and task logs before restarting. Keep workers
stopped for auth/quota failures; fix the cause before manually unblocking.
Back up board SQLite with services stopped plus the preserved worktrees;
never erase `.runtime` as a restart strategy. Rotate any exposed credential.

## Verified state — October 22, 2026

The pinned Hermes image and Codex 0.163.0 worker image both run. Image manifests:
Hermes `sha256:94802ccb76578df0e897289dd581578973a2d7ecafdbf6371044fd8af83942ef`;
worker `sha256:4d6347e8ee170d12fc564469c02985b79d1a89d5c34e21a561ccda34d216712b`.
The initial disk-full Docker failure recovered after explicitly approved installer
cleanup and R/RStudio removal. Existing Docker data and user projects were retained.
Two identified task build-cache records were removed. About 12 GiB host space
remains; the 20 GiB guard still blocks new builds. No rebuild is currently needed.

The default Docker filter prevented Bubblewrap namespace creation. The user
explicitly approved one-off tests of the worker-only pinned OpenAI syscall
profile. With that override, the actual no-model test passed as UID 10000:
workspace writes succeeded; home writes, Git metadata writes, and IP socket
creation were denied. No privileged mode, capabilities, host settings or controller
policy changed. Persistent use of this security override still needs approval.

A dedicated worker Codex device login succeeded. Native Hermes then imported
only that dedicated login into its own worker provider session. No desktop
credential or personal plugin was copied. The available coding model selected
through native Hermes is `gpt-6.1-sol`, low reasoning; this does not select the
scientific experiment model. Several bounded authenticated coding diagnostic
turns ran; no research experiments were executed.

Windows bind ownership caused native Hermes and Git ownership checks to fail.
`automation/compose.windows.yaml` instead uses four Linux-owned external named
volumes. `automation/seed_linux_state.py` seeds only this task's prepared homes,
board and bundled tracked Git history, as UID 10000 with no added capabilities.
Existing Windows state remains a backup. Completed seeds are idempotent; the
seed command does not synchronize subsequent code or credential changes. The
volumes are external so Compose teardown does not delete them.

On Windows, add `-f automation/compose.windows.yaml` to every runtime command
above after this one-time seed:

```powershell
python automation/seed_linux_state.py
```

The native callback was registered, but Codex deferred tool discovery and did
not forward board-routing variables. A small post-migration adapter fixes these
integration details; it does not schedule tasks. It exposes only Hermes's MCP
namespace directly and forwards only `HERMES_KANBAN_HOME` and
`HERMES_KANBAN_BOARD`. The user separately approved unattended reads through
`kanban_list` and `kanban_show`; no mutation tools are auto-approved. Reapply this
adapter after every native migration, only after equivalent operator approval:

```powershell
$helper = (Resolve-Path automation/configure_worker.py).Path
docker compose -f automation/compose.yaml -f automation/compose.windows.yaml run --rm --volume "${helper}:/smoke/configure_worker.py:ro" --entrypoint /opt/hermes/.venv/bin/python worker /smoke/configure_worker.py
```

Account app connectors appeared in the dedicated Codex tool catalog after the
ChatGPT login; no connected app data was read. Worker `features.apps=false`
disables them. The app-server metadata now confirms only `hermes-tools` remains exposed.
An actual authenticated `kanban_list` returned zero tasks from the shared
research board. The worker profile explicitly enables only the Kanban Hermes
toolset. Native Hermes may expose additional callback tool definitions; mutation
approval remains required, and sandbox restrictions do not cover MCP operations.

For an approved one-off sandbox test on Windows:

```powershell
$env:RESEARCH_WORKER_SECCOMP = (Resolve-Path automation/security-proposal/codex-security-seccomp.json).Path
$smokeSource = (Resolve-Path automation/sandbox_smoke.py).Path
docker compose -f automation/compose.yaml -f automation/compose.windows.yaml -f automation/security-proposal/compose.namespace.yaml run --rm --volume "${smokeSource}:/smoke/sandbox_smoke.py:ro" --entrypoint /opt/hermes/.venv/bin/python worker /smoke/sandbox_smoke.py
```

GitHub author association on prior pushed setup commits was verified as Nav1919.
Draft PR #32 was found closed and unmerged; publishing created draft PR #36.
Its head `fe7b563` passed both GitHub automation-test runs. The controller also
passed a separate authenticated native board-read turn, returning zero tasks. Offline tests cover identity, clean agent-branch
publishing, preparation, disk guards, callback permissions and sandbox failure
propagation; CI checks the baseline Compose file. Linux-volume seeding and actual
sandbox behavior have additional manual runtime evidence.

## Remaining activation gates

1. Finish Discord bot setup. A separate native controller OAuth login succeeded;
   no worker credential was copied. Verify the selected controller provider/model
   through a bounded board-read turn before starting its gateway (passed).
2. Approve persistent use of the tested worker syscall profile before services
   are started. Decide the minimal permitted Kanban mutation handoffs separately;
   only two read tools currently have unattended approval.
3. Complete one bounded card with a preserved agent worktree, tested edit, commit
   and review handoff. Git metadata writes are currently blocked by the Codex
   sandbox; a scoped commit handoff still needs implementation and verification.
4. Use the verified Git-bundle transfer below for host publishing. Never give
   the worker the host GitHub token as a shortcut.
5. Verify Discord progress/HITL round trip, native cron delivery and restart
   persistence before claiming a persistent deployment.
6. Select the scientific model/manifest and a provider-enforced spend allowance
   before paid experiments. Any required-CI policy change needs owner consent.

No persistent services, cron delivery or Discord delivery are claimed active.
No changes were merged. The setup remains an integration in progress, not an
unattended research deployment.

## Linux worker publishing handoff

With workers stopped, export the explicit clean agent branch and its actual
container worktree path:

```powershell
python automation/export_worker.py --branch agent/task-id --worktree /workspace/repo/.worktrees/task-id
python automation/manage.py publish --branch agent/task-id --source .runtime/handoffs/task-id/repo --title "Concrete milestone" --body-file review.md
```

The exporter mounts only the code volume read-only and a new handoff output
folder writable. It runs nonroot with no network, capabilities or credentials.
A native Git bundle carries tracked history to a fresh host checkout; no worker
Git config, hooks or runtime homes are copied. Host-side author checks and the
existing draft publisher remain mandatory. Refusal preserves partial output for
inspection; choose a new task/milestone directory rather than overwriting it.
The current implementation reserves one output directory per task ID; for later
milestones preserve/archive that task's previous handoff before exporting again.

The real Docker export reconstructed clean commit `41890fd` from the worker
volume and verified its author identity. A separate offline test checks actual
bundle creation/import, commit identity, wrong-author refusal and overwrite
refusal. This proves committed-history transport, not automatic worker commits.

## Inactive coding-permission proposal

`automation/security-proposal/coding-permissions.toml` extends Codex's native
`:workspace` permission profile to permit writes only to the isolated clone's
`/workspace/repo/.git` metadata, with shell network still disabled. This permits
local commits/worktrees; it cannot enforce branch names inside the clone, so the
host publisher still rejects main and wrong authors. It does not grant worker
home writes or host access. No permission profile has been activated.

Four additional proposed callback approvals cover heartbeat, comment, block and
request-review. Complete, unblock, task creation and review decisions remain
unapproved. MCP operations execute outside the shell sandbox; board mutation is
an explicit additional authority, scoped by available tool names rather than
by card ownership. The proposal needs consent before application or testing.

## October 22 bounded coding-permission test

The operator explicitly approved the coding-permission test after the earlier
pause. The worker's Codex configuration was snapshotted in memory, changed only
for a one-off container, and restored in `finally` afterward. No persistent
service or broader permission profile was activated.

The real no-model probe passed as UID 10000: workspace and isolated-clone Git
metadata writes succeeded; writes to `/opt/data` and `/board`, and IP socket
creation, were denied. This confirms the native `research-git` profile works
with the approved syscall override. The post-migration helper now has an
explicit `--allow-local-commits` opt-in; use it only within an approved test or
a separately approved deployment, never as part of default preparation.

A native Kanban card `t_2fb6efc4` was created with one attempt, 180 seconds,
`local-only` completion and branch `agent/orchestration-smoke`. Native dispatch
created `/workspace/repo/.worktrees/t_2fb6efc4` and launched the coder profile.
The worker failed while persisting its conversation, before any tracked edit or
commit. Native Hermes recorded exit 1 and auto-blocked the card after its first
failure. Its worktree remains clean at `41890fd`; preserve the card, native logs,
run history and pending journal for diagnosis. This is a failed end-to-end test.

The retained journal's failed operation was `session.sidecars`, patch key
`_usage_anchor`; the native worker reported `WorkerPersistenceError:
permission_denied` during persistence and token-accounting flush. Storage had
ample VM space and correct nonroot ownership. This narrows the issue to the
managed session persistence path; it does not prove which upstream ownership
check rejected it. No check was disabled or patched. Existing upstream pytest
regressions could not run because pytest is absent from the pinned runtime;
no package was installed to hide that limitation.

The one-pass dispatcher and its child PIDs must be inspected/reaped from the
**same container process namespace**. A separate `compose run` can read shared
SQLite state but cannot reliably judge another container's worker PID. For this
test the native reaper ran through `docker exec` in the original test container
with zero permitted spawns. Production uses one persistent worker dispatcher;
do not run competing dispatchers or cross-container PID reapers.

The current repository has 26 passing offline checks, including the opt-in
profile's exact Git scope, disabled network, six permitted callback names and
idempotence. A successful shell-permission probe is not evidence of a successful
managed worker or a completed research task. The failed card remains blocked
pending a diagnosed fix and deliberate operator restart, with no automatic retry.

Discord onboarding is in progress for a newly created Hermes Research app.
The user creates its credential in Discord and enters it only in the native
controller onboarding window. Do not place its token in this document, PR,
worker home, command arguments or chat. Verify token presence, owner allowlist,
intents and actual delivery before claiming the adapter active.
