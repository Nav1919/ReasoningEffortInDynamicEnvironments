"""Host setup and publishing boundary; Python 3.11+, stdlib only.

Run `python automation/manage.py --help` from the repo. Inputs are an authenticated
Git credential and explicit CLI arguments; outputs are isolated runtime files or
a draft PR. Never prints credential values. Tests: tests/test_automation.py.
Hermes, not this utility, owns scheduling, task state, and coding execution.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.error
import urllib.request

REPO = "Nav1919/ReasoningEffortInDynamicEnvironments"
ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=ROOT):
    return subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
                           "-c", "core.fsmonitor=false", *args], cwd=cwd, check=True, text=True,
                          capture_output=True).stdout.strip()


def credential():
    # Only the host publisher reads authentication. Nothing is copied to workers.
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    result = subprocess.run(["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n", text=True, capture_output=True,
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never"))
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if not fields.get("password"):
        raise ValueError("No noninteractive GitHub credential; authenticate on the host first")
    return fields["password"]


def api(path, token, payload=None):
    request = urllib.request.Request("https://api.github.com" + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json", "User-Agent": "research-setup"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def author_for(user, expected_login, email=None, verified_emails=()):
    if user["login"].casefold() != expected_login.casefold():
        raise ValueError("Authenticated GitHub account does not match requested author")
    name = user.get("name")
    if not name or not user.get("id"):
        raise ValueError("GitHub profile needs a name and numeric account ID")
    noreply = f'{int(user["id"])}+{user["login"]}@users.noreply.github.com'
    if email and email != noreply and email not in verified_emails:
        raise ValueError("Requested email is not verified for this account")
    return {"login": user["login"], "id": user["id"], "name": name,
            "email": email or noreply,
            "basis": "GitHub account ID noreply" if not email or email == noreply else "verified email"}


def identity(login, email=None):
    token = credential()
    user = api("/user", token)
    emails = []
    if email and not email.endswith("@users.noreply.github.com"):
        emails = [e["email"] for e in api("/user/emails", token) if e["verified"]]
    record = author_for(user, login, email, emails)
    git("config", "--local", "user.name", record["name"])
    git("config", "--local", "user.email", record["email"])
    git("config", "--local", "user.useConfigOnly", "true")
    state = ROOT / ".runtime"
    state.mkdir(exist_ok=True)
    (state / "identity.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


def prepare():
    state = ROOT / ".runtime"
    record = json.loads((state / "identity.json").read_text())
    # Refuse overwriting a previously configured deployment or its credentials.
    targets = [state / "controller", state / "worker", state / "board", state / "repo"]
    if any(p.exists() for p in targets):
        raise ValueError("Runtime already exists; inspect it rather than overwriting")
    for p in targets[:-1]:
        p.mkdir(parents=True)
    for role in ("controller", "worker"):
        config = (ROOT / "automation" / f"{role}.json").read_text()
        (state / role / "config.yaml").write_text(config)
    soul = (ROOT / "automation/controller-prompt.md").read_text()
    for document in ("AGENTS.md", "docs/weekly-tracker.md"):
        soul += "\n\n" + (ROOT / document).read_text(encoding="utf-8")
    (state / "controller/SOUL.md").write_text(soul, encoding="utf-8")
    profile = state / "worker/profiles/coder"
    profile.mkdir(parents=True)
    shutil.copyfile(state / "worker/config.yaml", profile / "config.yaml")
    (state / "worker/codex").mkdir()
    shutil.copyfile(ROOT / "automation/codex.toml", state / "worker/codex/config.toml")
    git("clone", "--no-local", "--no-hardlinks", str(ROOT), str(state / "repo"))
    target = state / "repo"
    git("remote", "set-url", "origin", f"https://github.com/{REPO}.git", cwd=target)
    git("config", "user.name", record["name"], cwd=target)
    git("config", "user.email", record["email"], cwd=target)
    git("config", "user.useConfigOnly", "true", cwd=target)
    git("config", "credential.helper", "", cwd=target)
    print("Prepared isolated runtime. No credentials copied; no services started.")


def agent_branch(branch):
    if not re.fullmatch(r"agent/[a-z0-9][a-z0-9_-]{0,63}", branch):
        raise ValueError("Use one agent/<task-id> branch; publishing main is forbidden")
    return branch


def publish(branch, title, body_file, source=ROOT):
    agent_branch(branch)
    if not title.strip() or not body_file.is_file():
        raise ValueError("A PR title and body file are required")
    token = credential()
    record = json.loads((ROOT / ".runtime/identity.json").read_text())
    author_for(api("/user", token), record["login"])
    if git("status", "--porcelain", cwd=source):
        raise ValueError("Commit or resolve changes before publishing")
    if git("branch", "--show-current", cwd=source) != branch:
        raise ValueError("Source checkout must be on the explicit publishing branch")
    info = api(f"/repos/{REPO}", token)
    base = info["default_branch"]
    commits = git("log", f"origin/{base}..{branch}", "--format=%an%x00%ae", cwd=source).splitlines()
    if not commits or any(c != record["name"] + "\0" + record["email"] for c in commits):
        raise ValueError("Every new commit must use the verified user author identity")
    # Push credentials remain on the host. Explicit destination prevents main pushes.
    push_env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_COUNT="1",
        GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
        GIT_CONFIG_VALUE_0="AUTHORIZATION: basic " + base64.b64encode(("x-access-token:" + token).encode()).decode())
    subprocess.run(["git", "-c", "core.hooksPath=" + os.devnull,
        "-c", "credential.helper=", "-c", "http.sslVerify=true", "push", f"https://github.com/{REPO}.git",
        f"{branch}:refs/heads/{branch}"], cwd=source, env=push_env,
        check=True, capture_output=True, text=True)
    body = body_file.read_text(encoding="utf-8") + (
        "\n\nAgent-assisted implementation: Codex; Hermes orchestration where configured. "
        "User-requested commit authorship is separate from authentication/pusher and signing. "
        "Human review and manual merge required. Deployment status is recorded in docs/automation.md.")
    existing = api(f"/repos/{REPO}/pulls?state=open&head={info['owner']['login']}:{branch}", token)
    pr = existing[0] if existing else api(f"/repos/{REPO}/pulls", token,
        {"title": title, "head": branch, "base": base, "body": body, "draft": True})
    # GitHub's commit representation is the actual association check, not git config.
    for page in range(1, 100):
        remote = api(f"/repos/{REPO}/pulls/{pr['number']}/commits?per_page=100&page={page}", token)
        for commit in remote:
            if (commit.get("author") or {}).get("login", "").casefold() != record["login"].casefold():
                raise ValueError("PR created, but commit profile association failed: " + pr["html_url"])
        if len(remote) < 100:
            break
    print(json.dumps({"pr": pr["html_url"], "author_association": record["login"], "draft": pr["draft"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    ident = commands.add_parser("identity")
    ident.add_argument("--login", required=True)
    ident.add_argument("--email")
    commands.add_parser("prepare")
    pub = commands.add_parser("publish")
    pub.add_argument("--branch", required=True)
    pub.add_argument("--title", required=True)
    pub.add_argument("--body-file", type=Path, required=True)
    pub.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        if args.command == "identity":
            identity(args.login, args.email)
        elif args.command == "prepare":
            prepare()
        else:
            publish(args.branch, args.title, args.body_file, args.source.resolve())
    except urllib.error.HTTPError as error:
        parser.exit(1, f"GitHub request failed: HTTP {error.code}. No credentials printed.\n")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Subprocess output may contain remote credential-helper messages; omit it.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        parser.exit(1, message + "\n")


if __name__ == "__main__":
    main()
