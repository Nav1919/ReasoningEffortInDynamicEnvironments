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

An active `Protect main` ruleset was observed through GitHub's read API. Classic
branch protection returned 404; no protection settings were changed. Human
review should inspect required checks and bypass actors before unattended use.
The CI workflow adds tests; it does not make them required or alter rulesets.

## Prepare and build

Requires Git, Python 3.11+, Docker Linux containers and sufficient disk/memory.
Run from the repository root. Preparation refuses to overwrite an existing
runtime. It copies **no credentials** and starts no services.

```bash
python automation/manage.py prepare
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
# /codex-runtime codex_app_server
```

That native command registers Hermes' callback MCP server in the dedicated
Codex home, enabling Kanban handoffs. Merely setting the YAML runtime field
does not perform this registration. Review its generated config; retain
workspace-write and disabled shell network. Test the actual sandbox before
launching a coding card. Do not copy personal plugins/MCP servers.

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
integration tests pass (12 tests); Compose configuration parses. The initial
Windows sandbox refused temporary Git repositories; rerun outside that sandbox
passed. Desktop Codex login was verified. Docker was initially stopped and was
started for build validation. Container build/runtime, sandbox smoke test,
Discord round-trip, cron delivery and restart persistence require separate
evidence; see the PR for the observed build outcome. No changes were merged.

Run checks: `python -m unittest discover -s tests -v` and
`docker compose -f automation/compose.yaml config --quiet`.
