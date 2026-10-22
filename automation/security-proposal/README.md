# Proposed worker-only namespace support — inactive until approved

The current default Docker syscall filter prevents Codex's Bubblewrap sandbox
from creating namespaces. This proposal reuses the unmodified seccomp allowlist
from OpenAI's Codex Security container, pinned in `provenance.json` with SHA-256
checksums and its upstream license. No new Docker image build is needed.

The separate Compose override replaces the worker's Docker syscall filter. It
allows namespace creation and mount-related operations, including `clone`,
`clone3`, `unshare`, `setns`, `mount` and `pivot_root`. These are additional
kernel operations relative to the current Docker filter, so this is a security
change, not simply a configuration repair. Its default action still denies
unlisted syscalls. The controller keeps its existing default filter.

The baseline worker's nonroot UID, `cap_drop: ALL`, no-new-privileges, limited
mounts, resource caps and Codex workspace-write/network-disabled policy remain.
It grants no privileged mode, Docker socket, host home or host networking. The
proposal does not change host sysctls or Docker daemon settings. The profile
alone may be insufficient on hosts with additional AppArmor restrictions; stop
on failure and review the evidence rather than silently relaxing another layer.

The original user instruction forbids security changes without consent. This
proposal has **not** been applied. With explicit approval, first run only an
unauthenticated one-shot sandbox smoke test, then enable for the worker only
if workspace writes pass and outside-workspace/Git metadata/network operations
are denied. Keep model credentials out until that test passes.

PowerShell, from the repository root after approval:

```powershell
$env:RESEARCH_WORKER_SECCOMP = (Resolve-Path automation/security-proposal/codex-security-seccomp.json).Path
docker compose -f automation/compose.yaml -f automation/security-proposal/compose.namespace.yaml config --quiet
```

Omitting the override returns to the baseline filter. Do not set
`seccomp=unconfined`, add `SYS_ADMIN`, enable privileged mode or disable the Codex
sandbox as a fallback.

Source: the `docker/codex-security-seccomp.json` and `compose.runner.yaml` files
in [OpenAI's Codex Security repository](https://github.com/openai/codex-security/tree/17c04c09e5896d9bbf1e1ea1b7c29622c7b14c64).
