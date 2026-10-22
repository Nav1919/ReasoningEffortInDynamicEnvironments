"""Apply the approved read-only callback policy to a dedicated worker home.

Run after native Hermes `codex-runtime migrate`: python configure_worker.py.
Reads CODEX_HOME/config.toml (default /opt/data/codex); changes only Hermes
callback visibility and approval for kanban_list/show. No credentials are read.
Refuses a missing native registration or relaxed sandbox. Tests:
tests/test_automation.py; actual authenticated board-read smoke in docs/automation.md.
"""
import os
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


def configure(content):
    settings = tomllib.loads(content)
    if (settings.get("sandbox_mode") != "workspace-write"
            or settings.get("approval_policy") != "never"
            or settings.get("sandbox_workspace_write", {}).get("network_access") is not False):
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
    tomllib.loads(content)
    return content


if __name__ == "__main__":
    path = Path(os.environ.get("CODEX_HOME", "/opt/data/codex")) / "config.toml"
    path.write_text(configure(path.read_text()))
    print("Hermes board reads configured; workspace sandbox retained")
