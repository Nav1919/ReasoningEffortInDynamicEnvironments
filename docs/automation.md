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

## Validation record

October 21, 2026: offline identity/branch/isolation and real temporary-Git
integration tests pass (14 tests, including disk preflight guards); Compose configuration parses. The initial
Windows sandbox refused temporary Git repositories; rerun outside that sandbox
passed. Draft PR #32 was published and GitHub associated every new commit with
Nav1919; both push and PR CI runs passed on head `62da0e9`. Desktop Codex login
was verified. Docker was initially stopped and was
started for build validation. A remote Git build stalled; an archive of the exact
same upstream commit then completed dependency installation and compilation.
Image extraction failed with **read-only file system** in Docker's internal
snapshot store; a subsequent read also returned **input/output error** and the
worker build could not write Docker's metadata DB. The image was initially unusable.
No Docker data was reset/pruned and no daemon security settings were changed.
The host C: drive had reached zero free bytes. Removing only this task's
temporary upstream source checkout/archive recovered about 0.6 GB. Existing
Docker images, volumes and caches were preserved. The added `preflight` command
blocks a new build below 20 GiB free; check Docker's VM allocation too. Do not
rebuild on the current low-space drive.

### Subsequent recovery and container smoke checks

Following user-approved installer cleanup and R/RStudio uninstallation, Docker
recovered without resetting its data or changing security settings. The Hermes
image became inspectable and its CLI ran successfully. Two specifically
identified temporary cache records from this task were removed (1.101 GB
logical cache); existing images and volumes were retained.

The Codex worker image built successfully and reported `codex-cli 0.163.0`.
Hermes recognized the dedicated `coder` profile, and the `research` board was
initialized under `/board/kanban/boards/research/kanban.db`. Both services use
Compose `init: true` so the direct nonroot entrypoint has a process reaper.

The actual no-model sandbox test failed before executing the test program:
`bwrap: No permissions to create a new namespace`. Workspace-write shell
execution in this container is therefore **blocked**, not verified safe or
ready for coding. No privileged mode, seccomp relaxation, sysctl or sandbox
bypass was applied. A compatible host/runtime or an explicitly approved,
reviewed namespace configuration is required before retrying. No model calls
or research experiments were made.

Docker unpacking/snapshotting consumed substantial space even for the worker
layer; the 20 GiB build guard remains in place for future builds. The final
observed host headroom was about 3.4 GiB. No further builds should run at that
headroom. User projects, scripts and data were preserved during app removal.

Remaining operator actions, in order:

1. Restore at least 20 GiB of host disk headroom before additional builds.
   Docker and the two images now work; no reset/rebuild is currently needed.
   Resolve the namespace restriction through a compatible runtime or an
   explicitly approved security configuration. Do not disable the sandbox.
2. Finish the dedicated controller/provider, Discord and container Codex logins
   above. Select the available coding model and register the native callback.
3. Verify nested sandbox behavior, one research worktree/commit/review handoff,
   Discord progress plus HITL reply, cron delivery and restart persistence.
4. Approve the experiment manifest/model and provider-enforced spend allowance
   before paid experiments. Require CI by policy only with owner consent.

No persistent agents, cron schedule or Discord delivery are claimed active.
No changes were merged. Container CLI checks passed; the sandbox smoke test
failed. Discord round-trip, cron delivery and restart persistence remain unverified.

Run checks: `python -m unittest discover -s tests -v` and
`docker compose -f automation/compose.yaml config --quiet`.

### Namespace diagnosis and pending approval

The worker reports no effective Linux capabilities, no-new-privileges enabled,
and Docker's built-in seccomp filter active. The kernel has a nonzero user
namespace limit; this supports a container syscall-filter restriction rather
than a conclusion that the kernel has no namespace support. Dedicated Codex
login status is `Not logged in`; no controller provider/Discord credential was
available. No desktop login or personal plugins were copied.

Native `codex-runtime migrate` completed successfully for `coder`, registered
only `hermes-tools`, and preserved `sandbox_mode=workspace-write` and
`network_access=false`. This proves registration, not authenticated model/tool
execution. The research board diagnostics reported no active issues.

`automation/security-proposal/` contains an **inactive**, unmodified OpenAI
Codex Security seccomp profile pinned to source commit
`17c04c09e5896d9bbf1e1ea1b7c29622c7b14c64`. Its license and file checksums are
included. A worker-only Compose override is prepared, with no host/daemon
changes, added capabilities, controller changes, or sandbox bypass. It allows
additional namespace/mount syscalls, so it requires explicit user approval
before even a one-shot runtime test. The proposal and combined Compose config
validate offline; neither has been applied.

The repeatable smoke runner preserves the child process's failing status and
produces JSON evidence. Against the unchanged baseline it exits 1 with the
Bubblewrap namespace error. After approval, use this same command with the
additional proposed Compose override; no model credentials are needed:

```powershell
$smokeSource = (Resolve-Path automation/sandbox_smoke.py).Path
docker compose -f automation/compose.yaml run --rm --volume "${smokeSource}:/smoke/sandbox_smoke.py:ro" --entrypoint /opt/hermes/.venv/bin/python worker /smoke/sandbox_smoke.py
```

The smoke runner first proves the worker home is writable outside the sandbox.
Inside it, repository writes must succeed while worker-home writes, Git metadata
writes and IP socket creation must fail. Failure prevents activation. The
offline suite additionally covers smoke failure propagation, root refusal,
and upstream profile integrity (17 total tests).
