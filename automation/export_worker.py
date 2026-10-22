"""Export a clean worker agent branch to the existing host publisher.

Run: python automation/export_worker.py --branch agent/task-id
Reads only the research-code Docker volume and local verified identity. Creates
a new .runtime/handoffs/task-id checkout via Git bundle; never pushes or reads
worker credentials. Run with workers stopped. Offline bundle tests live in
tests/test_automation.py; actual Docker export evidence is in docs/automation.md.
"""
import argparse
import json
from pathlib import PurePosixPath
import subprocess

import manage


def import_bundle(bundle, destination, branch, identity):
    manage.agent_branch(branch)
    if destination.exists():
        raise ValueError("Handoff checkout already exists; preserve it")
    # Git transports tracked history only; runtime homes and authentication never
    # cross this boundary. No worker-controlled Git config or hooks are imported.
    manage.git("clone", "--branch", branch, str(bundle), str(destination))
    manage.git("fetch", str(bundle), "refs/remotes/origin/main:refs/remotes/origin/main", cwd=destination)
    manage.git("remote", "set-url", "origin", f"https://github.com/{manage.REPO}.git", cwd=destination)
    for key, value in (("user.name", identity["name"]), ("user.email", identity["email"]),
                       ("user.useConfigOnly", "true"), ("credential.helper", "")):
        manage.git("config", key, value, cwd=destination)
    authors = manage.git("log", f"origin/main..{branch}", "--format=%an%x00%ae", cwd=destination).splitlines()
    if not authors or any(author != identity["name"] + "\0" + identity["email"] for author in authors):
        raise ValueError("Export preserved for review, but new commit authors do not match verified identity")
    if manage.git("status", "--porcelain", cwd=destination):
        raise ValueError("Imported checkout is not clean")
    return manage.git("rev-parse", "HEAD", cwd=destination)


def export(branch, worktree="/workspace/repo"):
    manage.agent_branch(branch)
    path = PurePosixPath(worktree)
    if not path.is_absolute() or path.parts[:2] != ("/", "workspace") or ".." in path.parts:
        raise ValueError("Worktree must be an absolute path inside /workspace")
    identity = json.loads((manage.ROOT / ".runtime/identity.json").read_text())
    target = manage.ROOT / ".runtime/handoffs" / branch.removeprefix("agent/")
    target.mkdir(parents=True, exist_ok=False)
    # The source volume is read-only and the helper has no network, secrets,
    # capabilities or Docker socket. Only its new handoff directory is writable.
    subprocess.run(["docker", "run", "--rm", "--user", "10000:10000",
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--mount",
        "type=volume,source=research-code,target=/workspace,readonly", "--mount",
        f"type=bind,source={target},target=/out", "--entrypoint", "/bin/sh",
        "hermes-research-base:4e58c721", "-ec",
        'test "$(git -C "$2" branch --show-current)" = "$1"; '
        'test -z "$(git -C "$2" status --porcelain)"; '
        'git -C "$2" bundle create /out/worker.bundle "$1" refs/remotes/origin/main',
        "export-worker", branch, str(path)], check=True)
    sha = import_bundle(target / "worker.bundle", target / "repo", branch, identity)
    print(json.dumps({"source": str(target / "repo"), "branch": branch, "commit": sha,
                      "published": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--worktree", default="/workspace/repo")
    args = parser.parse_args()
    export(args.branch, args.worktree)
