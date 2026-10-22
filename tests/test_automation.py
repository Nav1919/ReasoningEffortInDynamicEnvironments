"""Offline safety/integration tests. Run: python -m unittest discover -s tests -v.

Uses temporary Git repos and mocked GitHub responses, never a live credential.
Validates automation/manage.py's attribution, preparation, publishing boundaries,
and deployment credential separation. No research/model calls are made.
"""
import importlib.util
import hashlib
import errno
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("manage", ROOT / "automation/manage.py")
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)
smoke_spec = importlib.util.spec_from_file_location("smoke", ROOT / "automation/sandbox_smoke.py")
smoke = importlib.util.module_from_spec(smoke_spec)
smoke_spec.loader.exec_module(smoke)
USER = {"login": "Nav1919", "id": 75394407, "name": "Pranav Panicker"}
worker_spec = importlib.util.spec_from_file_location("worker_config", ROOT / "automation/configure_worker.py")
worker_config = importlib.util.module_from_spec(worker_spec)
worker_spec.loader.exec_module(worker_config)
snapshot_spec = importlib.util.spec_from_file_location("board_snapshot", ROOT / "automation/board_snapshot.py")
board_snapshot = importlib.util.module_from_spec(snapshot_spec)
snapshot_spec.loader.exec_module(board_snapshot)
export_spec = importlib.util.spec_from_file_location("export_worker", ROOT / "automation/export_worker.py")
export_worker = importlib.util.module_from_spec(export_spec)
with patch.dict(sys.modules, {"manage": manage}):
    export_spec.loader.exec_module(export_worker)


class BundleHandoffTests(unittest.TestCase):
    def test_export_refuses_main_and_outside_worktrees_before_docker(self):
        with patch.object(export_worker.subprocess, "run") as run:
            for branch, worktree in (("main", "/workspace/repo"),
                                     ("agent/test", "/opt/data"),
                                     ("agent/test", "/workspace/../opt/data")):
                with self.assertRaises(ValueError):
                    export_worker.export(branch, worktree)
            run.assert_not_called()

    def test_actual_bundle_preserves_commit_identity_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            manage.git("init", "-b", "main", cwd=source)
            record = manage.author_for(USER, "Nav1919")
            manage.git("config", "user.name", record["name"], cwd=source)
            manage.git("config", "user.email", record["email"], cwd=source)
            (source / "base.txt").write_text("base")
            manage.git("add", "base.txt", cwd=source)
            manage.git("commit", "-m", "Base", cwd=source)
            manage.git("update-ref", "refs/remotes/origin/main", "HEAD", cwd=source)
            manage.git("checkout", "-b", "agent/test", cwd=source)
            (source / "result.txt").write_text("tested milestone")
            manage.git("add", "result.txt", cwd=source)
            manage.git("commit", "-m", "Milestone", cwd=source)
            bundle = root / "worker.bundle"
            manage.git("bundle", "create", str(bundle), "agent/test", "refs/remotes/origin/main", cwd=source)
            destination = root / "handoff"
            sha = export_worker.import_bundle(bundle, destination, "agent/test", record)
            self.assertEqual(sha, manage.git("rev-parse", "HEAD", cwd=source))
            self.assertEqual((destination / "result.txt").read_text(), "tested milestone")
            self.assertEqual(manage.git("config", "user.email", cwd=destination), record["email"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                export_worker.import_bundle(bundle, destination, "agent/test", record)
            wrong = dict(record, email="unverified@example.com")
            with self.assertRaisesRegex(ValueError, "authors do not match"):
                export_worker.import_bundle(bundle, root / "wrong-author", "agent/test", wrong)


class MonitorSnapshotTests(unittest.TestCase):
    def test_reordering_and_heartbeat_do_not_trigger_a_changed_snapshot(self):
        first = [{"id": "b", "status": "running", "started_at": 1},
                 {"id": "a", "status": "blocked"}]
        second = [{"id": "a", "status": "blocked"},
                  {"id": "b", "status": "running", "started_at": 99, "heartbeat": 100}]
        self.assertEqual(board_snapshot.snapshot(first), board_snapshot.snapshot(second))
        second[1]["status"] = "review"
        self.assertNotEqual(board_snapshot.snapshot(first), board_snapshot.snapshot(second))

    def test_large_boards_are_explicitly_truncated(self):
        result = json.loads(board_snapshot.snapshot([{"id": str(i), "title": "x" * 900} for i in range(201)]))
        self.assertTrue(result["truncated"])
        self.assertEqual(result["total"], 201)
        self.assertEqual(len(result["tasks"]), 200)
        self.assertEqual(len(result["tasks"][0]["title"]), 600)


class CallbackPolicyTests(unittest.TestCase):
    def test_opt_in_coding_policy_is_scoped_and_idempotent(self):
        import tomllib
        content = worker_config.configure(self.baseline(), coding=True)
        self.assertEqual(content, worker_config.configure(content, coding=True))
        config = tomllib.loads(content)
        self.assertEqual(config["default_permissions"], "research-git")
        self.assertNotIn("sandbox_mode", config)
        self.assertNotIn("sandbox_workspace_write", config)
        profile = config["permissions"]["research-git"]
        self.assertEqual(profile["extends"], ":workspace")
        self.assertEqual(profile["filesystem"], {"/workspace/repo/.git": "write"})
        self.assertFalse(profile["network"]["enabled"])
        tools = config["mcp_servers"]["hermes-tools"]["tools"]
        self.assertEqual(set(tools), {"kanban_list", "kanban_show", "kanban_heartbeat",
            "kanban_comment", "kanban_block", "kanban_request_review"})

    def test_assigned_worktree_metadata_rule_is_exact_and_idempotent(self):
        import tomllib
        path = "/workspace/repo/.git/worktrees/t_1234abcd"
        content = worker_config.configure(self.baseline(), coding=True, worktree_git=path)
        self.assertEqual(content, worker_config.configure(content, coding=True, worktree_git=path))
        rules = tomllib.loads(content)["permissions"]["research-git"]["filesystem"]
        self.assertEqual(rules, {"/workspace/repo/.git": "write", path: "write"})
        for invalid in ("/opt/data", "/workspace/repo/.git/worktrees/../config", "/workspace/other/.git"):
            with self.assertRaises(ValueError):
                worker_config.configure(self.baseline(), coding=True, worktree_git=invalid)

    def baseline(self):
        return (ROOT / "automation/codex.toml").read_text() + '''
# managed by hermes-agent
[mcp_servers.hermes-tools]
command = "python"
# end hermes-agent managed section
'''

    def test_idempotent_read_policy_preserves_sandbox_and_routes_board(self):
        import tomllib
        result = worker_config.configure(self.baseline())
        self.assertEqual(result, worker_config.configure(result))
        config = tomllib.loads(result)
        self.assertEqual(config["sandbox_mode"], "workspace-write")
        self.assertFalse(config["sandbox_workspace_write"]["network_access"])
        server = config["mcp_servers"]["hermes-tools"]
        self.assertEqual(set(server["tools"]), {"kanban_list", "kanban_show"})
        self.assertEqual(server["env_vars"], ["HERMES_KANBAN_HOME", "HERMES_KANBAN_BOARD"])
        self.assertLess(result.index("[mcp_servers.hermes-tools.tools"), result.index(worker_config.END))

    def test_relaxed_sandbox_refused(self):
        with self.assertRaisesRegex(ValueError, "workspace sandbox"):
            worker_config.configure(self.baseline().replace('"workspace-write"', '"danger-full-access"'))

    def test_unregistered_callback_refused(self):
        with self.assertRaisesRegex(ValueError, "migration first"):
            worker_config.configure((ROOT / "automation/codex.toml").read_text())


class IdentityTests(unittest.TestCase):
    def test_verified_account_noreply(self):
        self.assertEqual(manage.author_for(USER, "nav1919")["email"],
                         "75394407+Nav1919@users.noreply.github.com")

    def test_other_account_refused(self):
        with self.assertRaises(ValueError):
            manage.author_for(USER, "somebody-else")

    def test_unverified_email_refused(self):
        for email in ("invented@example.com", "1+Nav1919@users.noreply.github.com"):
            with self.assertRaises(ValueError):
                manage.author_for(USER, "Nav1919", email)

    def test_explicit_verified_email(self):
        self.assertEqual(manage.author_for(USER, "Nav1919", "a@example.com",
                         ["a@example.com"])["email"], "a@example.com")

    def test_branch_restrictions(self):
        for branch in ("main", "master", "agent/../main", "agent/a:main", "--all", "agent/a b"):
            with self.assertRaises(ValueError):
                manage.agent_branch(branch)
        self.assertEqual(manage.agent_branch("agent/t_123"), "agent/t_123")


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        manage.git("init", "-b", "main", cwd=self.root)
        manage.git("config", "user.name", USER["name"], cwd=self.root)
        manage.git("config", "user.email", manage.author_for(USER, USER["login"])["email"], cwd=self.root)
        for name in ("automation", "docs"):
            (self.root / name).mkdir()
        for name in ("controller.json", "worker.json", "codex.toml", "controller-prompt.md"):
            (self.root / "automation" / name).write_bytes((ROOT / "automation" / name).read_bytes())
        (self.root / "AGENTS.md").write_text("Research policy")
        (self.root / "docs/weekly-tracker.md").write_text("Research plan")
        manage.git("add", ".", cwd=self.root)
        manage.git("commit", "-m", "Initial", cwd=self.root)
        (self.root / ".runtime").mkdir()
        (self.root / ".runtime/identity.json").write_text(json.dumps(manage.author_for(USER, "Nav1919")))

    def tearDown(self):
        self.tmp.cleanup()

    def test_prepare_isolated_clone_and_no_overwrite(self):
        # Default cwd was bound at import; route only prepare's source clone call.
        original_git = manage.git
        def local_git(*args, **kwargs):
            return original_git(*args, cwd=kwargs.get("cwd", self.root))
        with patch.object(manage, "ROOT", self.root), patch.object(manage, "git", side_effect=local_git):
            manage.prepare()
            with self.assertRaises(ValueError):
                manage.prepare()
        clone = self.root / ".runtime/repo"
        self.assertEqual(original_git("config", "user.email", cwd=clone),
                         manage.author_for(USER, "Nav1919")["email"])
        self.assertEqual(original_git("config", "credential.helper", cwd=clone), "")
        self.assertEqual(original_git("remote", "get-url", "origin", cwd=clone),
                         "https://github.com/" + manage.REPO + ".git")
        self.assertTrue((self.root / ".runtime/worker/profiles/coder/config.yaml").is_file())
        self.assertEqual(json.loads((self.root / ".runtime/worker/author-identity.json").read_text())["login"], "Nav1919")
        self.assertFalse((self.root / ".runtime/worker/.env").exists())

    def test_publish_main_refused_before_credential_access(self):
        with patch.object(manage, "credential") as cred:
            with self.assertRaises(ValueError):
                manage.publish("main", "title", self.root / "AGENTS.md")
            cred.assert_not_called()

    def test_publish_dirty_checkout_refused(self):
        with patch.object(manage, "ROOT", self.root), patch.object(manage, "credential", return_value="test"), patch.object(manage, "api", return_value=USER):
            with self.assertRaisesRegex(ValueError, "Commit or resolve"):
                manage.publish("agent/task", "title", self.root / "AGENTS.md", self.root)


class ConfigurationTests(unittest.TestCase):
    def test_proposed_profile_matches_upstream_checksums(self):
        proposal = ROOT / "automation/security-proposal"
        metadata = json.loads((proposal / "provenance.json").read_text())
        for name, record in metadata["files"].items():
            self.assertEqual(hashlib.sha256((proposal / name).read_bytes()).hexdigest(), record["sha256"])
        profile = json.loads((proposal / "codex-security-seccomp.json").read_text())
        self.assertEqual(profile["defaultAction"], "SCMP_ACT_ERRNO")
        self.assertNotIn("seccomp=", (ROOT / "automation/compose.yaml").read_text())

    def test_low_disk_blocks_build_before_contacting_docker(self):
        with patch.object(manage.shutil, "disk_usage") as usage, patch.object(manage.subprocess, "run") as run:
            usage.return_value.free = 1024 ** 3
            with self.assertRaisesRegex(ValueError, "Build blocked"):
                manage.preflight()
            run.assert_not_called()

    def test_disk_and_docker_preflight(self):
        with patch.object(manage.shutil, "disk_usage") as usage, patch.object(manage.subprocess, "run") as run:
            usage.return_value.free = 30 * 1024 ** 3
            manage.preflight()
            run.assert_called_once()

    def test_native_caps_and_human_review(self):
        for role in ("controller", "worker"):
            config = json.loads((ROOT / "automation" / f"{role}.json").read_text())
            self.assertFalse(config["kanban"]["review_dispatch"])
            self.assertEqual(config["kanban"]["max_in_progress"], 1)
            self.assertEqual(config["kanban"]["failure_limit"], 1)
        controller = json.loads((ROOT / "automation/controller.json").read_text())
        self.assertEqual(controller["kanban"]["dispatch_profiles"], [])

    def test_worker_mounts_no_controller_or_host_credentials(self):
        worker = (ROOT / "automation/compose.yaml").read_text().split("  worker:")[1]
        for forbidden in (".runtime/controller", "docker.sock", "GH_TOKEN", "DISCORD", "~/.codex", "privileged:"):
            self.assertNotIn(forbidden, worker)


class SandboxSmokeTests(unittest.TestCase):
    def test_read_only_mount_is_a_denied_write(self):
        with patch.object(smoke.os, "open", side_effect=OSError(errno.EROFS, "Read-only file system")):
            smoke.denied_write(Path("/opt/data"))

    def test_missing_path_is_not_mistaken_for_denied_write(self):
        with patch.object(smoke.os, "open", side_effect=FileNotFoundError(errno.ENOENT, "Missing path")):
            with self.assertRaises(FileNotFoundError):
                smoke.denied_write(Path("/missing"))

    def test_unexpected_write_is_removed_and_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with self.assertRaises(AssertionError):
                smoke.denied_write(directory)
            self.assertEqual(list(directory.iterdir()), [])

    def test_namespace_failure_is_not_reported_as_success(self):
        failure = subprocess.CompletedProcess([], 1, "", "bwrap: No permissions to create a new namespace")
        with patch.object(smoke.os, "geteuid", return_value=10000, create=True), patch.object(smoke.tempfile, "NamedTemporaryFile"), patch.object(smoke.subprocess, "run", return_value=failure) as command:
            self.assertEqual(smoke.main(), 1)
            self.assertEqual(command.call_args.args[0][:3], ["/usr/local/bin/codex", "sandbox", "--"])

    def test_root_execution_refused(self):
        with patch.object(smoke.os, "geteuid", return_value=0, create=True):
            with self.assertRaisesRegex(AssertionError, "nonroot"):
                smoke.main()


class WorkerSurfaceTests(unittest.TestCase):
    def test_worker_cli_excludes_hermes_shell_tools(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "automation/worker.json").read_text())
        self.assertEqual(config["platform_toolsets"]["cli"], ["kanban"])
        self.assertEqual(config["model"]["openai_runtime"], "codex_app_server")


class PublisherTests(unittest.TestCase):
    def test_draft_pr_and_actual_profile_association(self):
        self.run_publish("Nav1919")

    def test_misattributed_remote_commit_refused(self):
        with self.assertRaisesRegex(ValueError, "profile association failed"):
            self.run_publish("different-user")

    def run_publish(self, remote_author):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".runtime").mkdir()
            record = manage.author_for(USER, "Nav1919")
            (root / ".runtime/identity.json").write_text(json.dumps(record))
            body = root / "body.md"
            body.write_text("Checks: offline tests pass")
            def fake_git(*args, **kwargs):
                if args[0] == "status": return ""
                if args[0] == "branch": return "agent/task"
                if args[0] == "log": return record["name"] + "\0" + record["email"]
                raise AssertionError(args)
            def fake_api(path, token, payload=None):
                if path == "/user": return USER
                if path.endswith("/commits?per_page=100&page=1"):
                    return [{"author": {"login": remote_author}}]
                if "?state=open" in path: return []
                if path.endswith("/pulls"):
                    self.assertTrue(payload["draft"])
                    self.assertIn("Agent-assisted", payload["body"])
                    return {"number": 1, "html_url": "https://github.com/example/pull/1", "draft": True}
                return {"default_branch": "main", "owner": {"login": "Nav1919"}}
            with patch.object(manage, "ROOT", root), patch.object(manage, "credential", return_value="secret-test-token"), patch.object(manage, "git", side_effect=fake_git), patch.object(manage, "api", side_effect=fake_api), patch.object(manage.subprocess, "run") as push:
                try:
                    manage.publish("agent/task", "Test change", body, root)
                finally:
                    command = push.call_args.args[0]
                    self.assertEqual(command[-1], "agent/task:refs/heads/agent/task")
                    self.assertNotIn("secret-test-token", " ".join(command))
                    self.assertIn("core.hooksPath=" + manage.os.devnull, command)


if __name__ == "__main__":
    unittest.main()
