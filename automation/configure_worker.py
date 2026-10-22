"""Configure callback routing and explicitly approved worker permissions.

Run after native Hermes `codex-runtime migrate`: python configure_worker.py.
Reads CODEX_HOME/config.toml (default /opt/data/codex). Default changes only
callback routing/visibility and kanban_list/show approval. The opt-in
--allow-local-commits selects the separately consent-gated coding proposal;
restore the original config after a bounded test. No credentials are read.
Refuses a missing native registration or relaxed sandbox. Tests:
tests/test_automation.py; actual authenticated board-read smoke in docs/automation.md.
"""
import os
import re
import argparse
from pathlib import Path
import tomllib

END = "# end hermes-agent managed section"
DIRECT = '''
[features.code_mode]
enabled = true
direct_only_tool_namespaces = ["mcp__hermes-tools", "mcp__hermes_tools"]
'''
READ_POLICY = '''
# User-approved unattended board reads only; reapply after native migration.
[mcp_servers.hermes-tools.tools.kanban_list]
approval_mode = "approve"
[mcp_servers.hermes-tools.tools.kanban_show]
approval_mode = "approve"
'''


def configure(content, coding=False, worktree_git=None):
    if worktree_git is not None and (not coding or not re.fullmatch(r"/workspace/repo/\.git/worktrees/t_[a-z0-9]+", worktree_git)):
        raise ValueError("Expected assigned Git metadata inside the isolated clone")
    settings = tomllib.loads(content)
    legacy = (settings.get("sandbox_mode") == "workspace-write"
              and settings.get("sandbox_workspace_write", {}).get("network_access") is False)
    named = False
    if coding and "sandbox_mode" not in settings and "sandbox_workspace_write" not in settings:
        proposal = (Path(__file__).parent / "security-proposal/coding-permissions.toml").read_text()
        expected = tomllib.loads(proposal.split("# Proposed callback approvals", 1)[0])["permissions"]["research-git"]
        if worktree_git:
            expected["filesystem"][worktree_git] = "write"
        named = (settings.get("default_permissions") == "research-git"
                 and settings.get("permissions", {}).get("research-git") == expected)
    if settings.get("approval_policy") != "never" or not (legacy or named):
        raise ValueError("Expected workspace sandbox and disabled shell network")
    if "hermes-tools" not in settings.get("mcp_servers", {}) or content.count(END) != 1:
        raise ValueError("Run native Hermes callback migration first")
    # Codex filters the subprocess environment. Forward only the nonsecret board
    # routing variables, otherwise the callback reads a separate profile board.
    server = settings["mcp_servers"]["hermes-tools"]
    board_vars = ["HERMES_KANBAN_HOME", "HERMES_KANBAN_BOARD"]
    if "env_vars" not in server:
        content = content.replace("[mcp_servers.hermes-tools]\n",
            '[mcp_servers.hermes-tools]\nenv_vars = ["HERMES_KANBAN_HOME", "HERMES_KANBAN_BOARD"]\n', 1)
    elif server["env_vars"] != board_vars:
        raise ValueError("Existing callback environment forwarding requires review")
    # Keep policy inside Hermes' managed section so subsequent native migration
    # does not mistake nested tool tables for a user-owned replacement transport.
    if READ_POLICY.strip() not in content:
        if settings["mcp_servers"]["hermes-tools"].get("tools"):
            raise ValueError("Existing callback tool policy requires review")
        content = content.replace(END, READ_POLICY + "\n" + END)
    mode = settings.get("features", {}).get("code_mode")
    if mode is None:
        content += DIRECT
    elif mode != tomllib.loads(DIRECT)["features"]["code_mode"]:
        raise ValueError("Existing code-mode configuration requires review")
    if coding:
        proposal = (Path(__file__).parent / "security-proposal/coding-permissions.toml").read_text()
        permissions, tools = proposal.split("# Proposed callback approvals", 1)
        tools = tools[tools.index("[mcp_servers."):]
        if worktree_git:
            permissions = permissions.replace("[permissions.research-git.filesystem]", '[permissions.research-git.filesystem]\n"' + worktree_git + '" = "write"')
        parsed = tomllib.loads(content)
        existing = parsed.get("permissions", {}).get("research-git")
        expected = tomllib.loads(permissions)["permissions"]["research-git"]
        if existing is None:
            content += "\n" + permissions
        elif existing != expected:
            raise ValueError("Existing coding permission profile requires review")
        if tools.strip() not in content:
            content = content.replace(END, tools + "\n" + END)
        selected = parsed.get("default_permissions", ":workspace")
        if selected not in (":workspace", "research-git"):
            raise ValueError("Existing selected permissions require review")
        if 'default_permissions = ":workspace"' in content:
            content = content.replace('default_permissions = ":workspace"', 'default_permissions = "research-git"', 1)
        elif "default_permissions" not in parsed:
            content = 'default_permissions = "research-git"\n' + content
    if coding:
        # Legacy sandbox settings take precedence over default_permissions. Remove
        # them only after the exact approved named profile was checked/installed.
        content = re.sub(r'^sandbox_mode\s*=.*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\[sandbox_workspace_write\]\s*\n.*?(?=^\[|\Z)', '',
                         content, flags=re.MULTILINE | re.DOTALL)
    tomllib.loads(content)
    return content


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-local-commits", action="store_true",
        help="Only after explicit approval: select the proposed Git and four handoff permissions")
    parser.add_argument("--worktree-git", help="Exact assigned worktree Git directory inside the approved isolated clone")
    args = parser.parse_args()
    path = Path(os.environ.get("CODEX_HOME", "/opt/data/codex")) / "config.toml"
    path.write_text(configure(path.read_text(), coding=args.allow_local_commits, worktree_git=args.worktree_git))
    print("Hermes callback configured; workspace sandbox and disabled shell network retained")
