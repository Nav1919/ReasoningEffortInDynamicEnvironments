"""Offline safety/integration tests. Run: python -m unittest discover -s tests -v.

Uses temporary Git repos and mocked GitHub responses, never a live credential.
Validates automation/manage.py's attribution, preparation, publishing boundaries,
and deployment credential separation. No research/model calls are made.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("manage", ROOT / "automation/manage.py")
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)
USER = {"login": "Nav1919", "id": 75394407, "name": "Pranav Panicker"}


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
