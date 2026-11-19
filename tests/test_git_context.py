"""Exercise the Git preflight through its public CLI on isolated repositories."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CONTEXT = Path(__file__).resolve().parents[1] / "plugins/talon/skills/git/scripts/context.py"


@unittest.skipUnless(shutil.which("git"), "Git is required for the preflight fixtures")
class GitContextTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.parent = Path(temp.name).resolve()
        self.repo = self.parent / "Git fixture é"
        self.repo.mkdir()
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith("GIT_") and key != "EMAIL"
        }
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, LC_ALL="C")
        self.git("init", "-q")
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        self.git("config", "user.useConfigOnly", "true")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], env=self.env, capture_output=True, check=True,
        ).stdout

    def configure_identity(self):
        self.git("config", "user.name", "Fixture User")
        self.git("config", "user.email", "fixture@example.test")

    def inspect(self, *flags, repo=None, env=None, exit_code=0):
        result = subprocess.run(
            [sys.executable, str(CONTEXT), "--repo", str(repo or self.repo), *flags],
            env=self.env if env is None else env, capture_output=True, text=True, encoding="utf-8",
            timeout=10,
        )
        self.assertEqual(result.returncode, exit_code, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1)
        return json.loads(result.stdout), result.stdout

    def test_unborn_branch_and_effective_identities_from_subdirectory(self):
        self.configure_identity()
        self.git("config", "committer.name", "Local Committer")
        nested = self.repo / "nested folder"
        nested.mkdir()
        env = dict(self.env, GIT_AUTHOR_NAME="Env Author", GIT_AUTHOR_EMAIL="author@example.test")

        context, _ = self.inspect("--require-identity", repo=nested, env=env)

        self.assertEqual(Path(context["root"]), self.repo)
        self.assertEqual(context["branch"], "main")
        self.assertTrue(context["unborn"])
        self.assertFalse(context["detached"])
        self.assertEqual(context["dirty"], dict(staged=0, unstaged=0, untracked=0))
        self.assertIsNone(context["upstream"])
        self.assertIsNone(context["ahead"])
        self.assertIsNone(context["behind"])
        self.assertEqual(context["identity"], {
            "author": {"name": "Env Author", "email": "author@example.test"},
            "committer": {"name": "Local Committer", "email": "fixture@example.test"},
            "missing": [],
        })

    def test_dirty_counts_skip_rename_source_and_keep_paths_private(self):
        self.configure_identity()
        old_name = "? private-rename-source\npart" if os.name != "nt" else "private-rename-source part"
        old = self.repo / old_name
        old.write_text("original\n", encoding="utf-8")
        self.git("add", "--", old_name)
        self.git("commit", "-qm", "fixture")
        new = self.repo / "private-rename-target"
        self.git("mv", "--", old_name, new.name)
        new.write_text("edited after staging\n", encoding="utf-8")
        new_dir = self.repo / "untracked"
        new_dir.mkdir()
        (new_dir / "private-first").touch()
        (new_dir / "private-second").touch()
        index = self.repo / ".git/index"
        initial_index = (index.read_bytes(), index.stat().st_mtime_ns)

        context, raw = self.inspect()

        self.assertEqual(context["dirty"], dict(staged=1, unstaged=1, untracked=2))
        self.assertNotIn("private-", raw)
        self.assertFalse(context["unborn"])
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), initial_index)

    def test_local_upstream_may_be_missing_or_diverged(self):
        self.configure_identity()
        self.git("commit", "--allow-empty", "-qm", "common")
        self.git("remote", "add", "origin", "https://example.invalid/private-remote-token")
        self.git("config", "branch.main.remote", "origin")
        self.git("config", "branch.main.merge", "refs/heads/main")

        context, raw = self.inspect()
        self.assertEqual(context["upstream"], "origin/main")
        self.assertIsNone(context["ahead"])
        self.assertIsNone(context["behind"])
        self.assertNotIn("private-remote-token", raw)

        self.git("checkout", "-q", "--detach", "HEAD")
        self.git("commit", "--allow-empty", "-qm", "upstream only")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        detached, _ = self.inspect()
        self.assertTrue(detached["detached"])
        self.assertIsNone(detached["branch"])
        self.assertIsNone(detached["upstream"])

        self.git("checkout", "-q", "main")
        self.git("commit", "--allow-empty", "-qm", "local only one")
        self.git("commit", "--allow-empty", "-qm", "local only two")
        context, _ = self.inspect()
        self.assertEqual((context["ahead"], context["behind"]), (2, 1))

    def test_detached_marker_can_be_a_branch_name(self):
        self.configure_identity()
        self.git("symbolic-ref", "HEAD", "refs/heads/(detached)")
        context, _ = self.inspect()
        self.assertEqual(context["branch"], "(detached)")
        self.assertFalse(context["detached"])

    def test_unresolved_and_empty_identities_only_fail_in_strict_mode(self):
        context, _ = self.inspect()
        self.assertEqual(context["identity"], {"author": None, "committer": None, "missing": ["author", "committer"]})
        strict, _ = self.inspect("--require-identity", exit_code=2)
        self.assertEqual(strict, context)

        self.configure_identity()
        for field, value, missing in [("EMAIL", "", "author.email"), ("NAME", "", "author")]:
            with self.subTest(field=field):
                env = {**self.env, f"GIT_AUTHOR_{field}": value}
                context, _ = self.inspect("--require-identity", env=env, exit_code=2)
                self.assertEqual(context["identity"]["missing"], [missing])

    def test_invalid_worktree_and_missing_git_have_distinct_errors(self):
        env = dict(self.env, GIT_DIR=str(self.repo / ".git"), GIT_WORK_TREE=str(self.repo))
        context, _ = self.inspect("--require-identity", repo=self.parent, env=env, exit_code=1)
        self.assertEqual(context, {"error": "GitWorktreeUnavailable"})
        empty_path = self.parent / "empty-path"
        empty_path.mkdir()
        context, _ = self.inspect(env=dict(self.env, PATH=str(empty_path)), exit_code=1)
        self.assertEqual(context, {"error": "GitUnavailable"})

    def test_status_skips_repository_configured_clean_filter_and_fsmonitor(self):
        self.configure_identity()
        (self.repo / ".gitattributes").write_text("filtered filter=fixture\n", encoding="utf-8")
        target = self.repo / "filtered"
        target.write_text("indexed\n", encoding="utf-8")
        self.git("add", "--", ".gitattributes", target.name)
        self.git("commit", "-qm", "fixture")
        self.git("config", "filter.fixture.clean", "touch invoked-filter; cat")
        self.git("config", "core.fsmonitor", "touch invoked-monitor")
        target.write_text("a different size and content\n", encoding="utf-8")

        context, _ = self.inspect()

        self.assertTrue(context["external_filters_disabled"])
        self.assertEqual(context["dirty"], dict(staged=0, unstaged=1, untracked=0))
        self.assertFalse((self.repo / "invoked-filter").exists())
        self.assertFalse((self.repo / "invoked-monitor").exists())


if __name__ == "__main__":
    unittest.main()
