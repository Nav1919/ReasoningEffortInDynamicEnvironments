"""Seed Docker Desktop's Linux-owned state without deleting Windows backups.

Run `python automation/seed_linux_state.py` after manage.py prepare. Inputs are
only this checkout's .runtime homes/board and verified identity. Outputs are
four named Docker volumes. Existing completed seeds are retained; unexpected
partially populated homes are refused. No credentials are printed or imported
from the desktop user's home. Validated with the actual Docker ownership and
Hermes/Codex integration smoke checks in docs/automation.md.
"""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "hermes-research-base:4e58c721"


def seed(volume, source, script, environment=()):
    # The image's /opt/data is owned by UID 10000; Docker volume copy-up retains
    # that owner. All copying then runs unprivileged, with no added capabilities.
    command = ["docker", "run", "--rm", "--user", "10000:10000", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--mount",
        f"type=volume,source={volume},target=/opt/data", "--mount",
        f"type=bind,source={source},target=/seed,readonly"]
    for item in environment:
        command.extend(["--env", item])
    command.extend(["--entrypoint", "/bin/sh", IMAGE, "-ec", script])
    subprocess.run(command, check=True)


def main():
    state = ROOT / ".runtime"
    identity = json.loads((state / "identity.json").read_text())
    # A bundle transports tracked history without running upload-pack against
    # the root-owned Windows mount or importing working-tree secrets/settings.
    subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull, "bundle", "create",
                    str(state / "seed.bundle"), "--all"], cwd=ROOT, check=True)
    for role in ("controller", "worker", "board"):
        source = state / role
        if not source.is_dir():
            raise SystemExit("Prepare the dedicated runtime before seeding Linux state")
        volume = "research-board" if role == "board" else "research-" + role + "-home"
        seed(volume, source, """
if [ -f /opt/data/.research-seeded ]; then exit 0; fi
if [ -e /opt/data/config.yaml ] || [ -e /opt/data/kanban.db ]; then
  echo 'Refusing to overwrite partially populated volume' >&2; exit 1
fi
cp -R /seed/. /opt/data/
find /opt/data -type d -exec chmod 700 {} +
find /opt/data -type f -name 'auth.json' -exec chmod 600 {} +
find /opt/data -type f -name 'config.*' -exec chmod 600 {} +
touch /opt/data/.research-seeded
chmod 600 /opt/data/.research-seeded
""")
        print("Linux-owned state ready: " + role)
    seed("research-code", ROOT, """
if [ -f /opt/data/.research-code-seeded ]; then exit 0; fi
if [ -e /opt/data/repo ]; then echo 'Refusing to overwrite an existing code directory' >&2; exit 1; fi
git clone /seed/.runtime/seed.bundle /opt/data/repo
git -C /opt/data/repo remote set-url origin https://github.com/Nav1919/ReasoningEffortInDynamicEnvironments.git
git -C /opt/data/repo config user.name "$RESEARCH_AUTHOR_NAME"
git -C /opt/data/repo config user.email "$RESEARCH_AUTHOR_EMAIL"
git -C /opt/data/repo config user.useConfigOnly true
git -C /opt/data/repo config credential.helper ''
touch /opt/data/.research-code-seeded
chmod 600 /opt/data/.research-code-seeded
""", ("RESEARCH_AUTHOR_NAME=" + identity["name"], "RESEARCH_AUTHOR_EMAIL=" + identity["email"]))
    print("Linux-owned code checkout ready; original host state preserved")


if __name__ == "__main__":
    main()
