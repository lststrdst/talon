"""Exercise the evaluation CLI against passing and failing disposable submissions."""

import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


CHECKS = Path(__file__).resolve().parents[1] / "plugins/talon/skills/checks"
SCRIPT = CHECKS / "scripts/agent_eval.py"
RETRY_CONTROL = CHECKS / "assets/retry/retry_contract.py"
GIT_TASK = "git-selective-commit"
RETRY_TASK = "sqlite-retry-regression"
README_ADDITION = b"\nRun the checks with `python3 -m unittest discover`.\n"
evaluator = runpy.run_path(str(SCRIPT))


def sandbox_available():
    if sys.platform.startswith("linux"):
        try:
            evaluator["require_linux_sandbox"]()
        except evaluator["EvalError"]:
            return False
        return True
    return sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file()


RETRY_SANDBOX = sandbox_available()


class AgentEvalTest(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory(prefix="talon eval ")
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name) / "scenario"
        self.repo = self.root / "workspace"
        self.env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR") if key in os.environ}
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", LC_ALL="C")

    def invoke(self, command, task, *flags, status):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), command, task, str(self.root), *flags], env=self.env,
            capture_output=True, text=True, encoding="utf-8", timeout=40,
        )
        self.assertEqual(completed.stderr, "")
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], status, report)
        self.assertEqual(completed.returncode, {"prepared": 0, "pass": 0, "fail": 1, "error": 2}[status])
        self.assertEqual(report["task"], task)
        self.assertEqual(report["version"], 1)
        return report

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], env=self.env, check=True,
            capture_output=True, timeout=10,
        ).stdout

    def edit_readme(self):
        with (self.repo / "README.md").open("ab") as readme:
            readme.write(README_ADDITION)

    def test_linux_sandbox_denies_start_before_running_candidate(self):
        probe = evaluator["require_linux_sandbox"]
        with patch.dict(probe.__globals__, sandbox_command=lambda *args: [sys.executable, "-c", "exit(1)"]):
            with self.assertRaisesRegex(evaluator["EvalError"], "retry_sandbox_unavailable"):
                probe()

    def test_unprepared_path_and_existing_destination(self):
        self.root.mkdir()
        (self.root / "private.txt").write_text("untouched\n", encoding="utf-8")
        self.assertEqual(self.invoke("grade", RETRY_TASK, status="error")["error"], "invalid_fixture")
        self.assertEqual(self.invoke("prepare", RETRY_TASK, status="error")["error"], "FileExistsError")
        self.assertEqual((self.root / "private.txt").read_text(encoding="utf-8"), "untouched\n")

    @unittest.skipUnless(shutil.which("git"), "Git is required for the Git fixture")
    def test_git_accepts_one_readme_commit_and_exact_local_push(self):
        self.invoke("prepare", GIT_TASK, "--push", status="prepared")
        base = self.git("rev-parse", "HEAD")
        staged = self.git("show", ":draft.txt")
        self.edit_readme()
        self.git("commit", "-qm", "Document checks", "--", "README.md")
        report = self.invoke("grade", GIT_TASK, status="fail")
        self.assertFalse(report["checks"]["pushed_to_local_origin"])
        self.git("push", "-q", "origin", "main")
        report = self.invoke("grade", GIT_TASK, status="pass")
        self.assertEqual(report["evidence"]["head"], report["evidence"]["remote_head"])
        self.assertNotEqual(self.git("rev-parse", "HEAD"), base)
        self.assertEqual(self.git("show", ":draft.txt"), staged)

    @unittest.skipUnless(shutil.which("git"), "Git is required for the Git fixture")
    def test_git_rejects_a_commit_that_consumed_the_staged_draft(self):
        self.invoke("prepare", GIT_TASK, status="prepared")
        report = self.invoke("grade", GIT_TASK, status="fail")
        self.assertTrue(report["checks"]["index_preserved"])
        self.assertFalse(report["checks"]["one_new_commit"])
        self.edit_readme()
        self.git("add", "--", "README.md")
        self.git("commit", "-qm", "Mistakenly include draft")
        report = self.invoke("grade", GIT_TASK, status="fail")
        self.assertFalse(report["checks"]["readme_only_commit"])

    @unittest.skipUnless(shutil.which("git"), "Git is required for the Git fixture")
    def test_git_rejects_a_correct_commit_if_the_original_index_is_reset(self):
        self.invoke("prepare", GIT_TASK, status="prepared")
        self.edit_readme()
        self.git("commit", "-qm", "Document checks", "--", "README.md")
        self.git("reset", "-q", "HEAD", "--", "draft.txt")
        report = self.invoke("grade", GIT_TASK, status="fail")
        self.assertTrue(report["checks"]["readme_only_commit"])
        self.assertFalse(report["checks"]["index_preserved"])

    @unittest.skipUnless(shutil.which("git"), "Git is required for the Git fixture")
    def test_readme_accepts_a_valid_paragraph_with_crlf_and_extra_blank_lines(self):
        self.invoke("prepare", GIT_TASK, status="prepared")
        readme = self.repo / "README.md"
        content = readme.read_bytes() + b"\n" + README_ADDITION.rstrip(b"\n")
        readme.write_bytes(content.replace(b"\n", b"\r\n"))
        self.git("commit", "-qm", "Document checks", "--", "README.md")
        self.invoke("grade", GIT_TASK, status="pass")

    def test_retry_does_not_execute_without_permission_or_with_changed_service(self):
        self.invoke("prepare", RETRY_TASK, status="prepared")
        shutil.copyfile(RETRY_CONTROL, self.repo / "test_retry.py")
        report = self.invoke("grade", RETRY_TASK, status="error")
        self.assertEqual(report["error"], "retry_execution_requires_opt_in")
        (self.repo / "retry_fixture.py").write_text("", encoding="utf-8")
        report = self.invoke("grade", RETRY_TASK, "--run-candidate-tests", status="fail")
        self.assertFalse(report["checks"]["service_unchanged"])

    @unittest.skipUnless(RETRY_SANDBOX, "A supported OS sandbox is required for test replay")
    def test_retry_grades_the_same_executed_tests_on_fresh_buggy_and_corrected_services(self):
        self.invoke("prepare", RETRY_TASK, status="prepared")
        shutil.copyfile(RETRY_CONTROL, self.repo / "test_retry.py")
        report = self.invoke("grade", RETRY_TASK, "--run-candidate-tests", status="pass")
        self.assertEqual(report["evidence"], {
            "buggy": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0},
            "corrected": {"tests": 2, "failures": 0, "errors": 0, "skipped": 0},
            "wrong_response_id": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0},
            "replaced_row_id": {"tests": 2, "failures": 1, "errors": 0, "skipped": 0},
        })

    @unittest.skipUnless(RETRY_SANDBOX, "A supported OS sandbox is required for test replay")
    def test_retry_rejects_missing_response_or_persisted_id_assertions(self):
        self.invoke("prepare", RETRY_TASK, status="prepared")
        control = RETRY_CONTROL.read_text(encoding="utf-8")
        count_only = "        self.assertEqual(len(read_orders(self.store)), 1)"
        for source, missing in (
            (control.replace("        self.assertEqual(retry_id, order_id)\n", ""), "checks_response_id"),
            (control.replace("        self.assertEqual(read_orders(self.store), original_rows)", count_only),
             "checks_persisted_id"),
        ):
            with self.subTest(missing=missing):
                (self.repo / "test_retry.py").write_text(source, encoding="utf-8")
                report = self.invoke("grade", RETRY_TASK, "--run-candidate-tests", status="fail")
                self.assertTrue(report["checks"]["same_retry_test"])
                self.assertFalse(report["checks"][missing])

    @unittest.skipUnless(RETRY_SANDBOX, "A supported OS sandbox is required for test replay")
    def test_retry_replay_does_not_allow_reading_the_parent_fixture(self):
        self.invoke("prepare", RETRY_TASK, status="prepared")
        control = RETRY_CONTROL.read_text(encoding="utf-8")
        outside = str(self.root.resolve() / "evaluation.json")
        test = f"""

class SandboxTest(unittest.TestCase):
    def test_file_outside_replay_is_inaccessible(self):
        with self.assertRaises(OSError):
            Path({outside!r}).read_bytes()
"""
        (self.repo / "test_retry.py").write_text(control + test, encoding="utf-8")
        report = self.invoke("grade", RETRY_TASK, "--run-candidate-tests", status="pass")
        self.assertEqual(report["evidence"]["corrected"]["tests"], 3)

    @unittest.skipUnless(RETRY_SANDBOX, "A supported OS sandbox is required for test replay")
    def test_retry_rejects_empty_skipped_or_unrelated_failures(self):
        self.invoke("prepare", RETRY_TASK, status="prepared")
        test_path = self.repo / "test_retry.py"
        for source, counts in (
            ("# No tests\n", (0, 0, 0, 0)),
            ("    @unittest.skip('not run')\n    def test_result(self): pass\n", (1, 0, 0, 1)),
            ("    def test_result(self): self.fail('unrelated')\n", (1, 1, 0, 0)),
            ("    def test_result(self): raise RuntimeError('unrelated')\n", (1, 0, 1, 0)),
        ):
            with self.subTest(source=source):
                if source.startswith("    "):
                    source = "import unittest\nclass CandidateTest(unittest.TestCase):\n" + source
                test_path.write_text(source, encoding="utf-8")
                result = self.invoke("grade", RETRY_TASK, "--run-candidate-tests", status="fail")
                self.assertFalse(result["checks"]["same_retry_test"])
                self.assertEqual(tuple(result["evidence"]["buggy"].values()), counts)


if __name__ == "__main__":
    unittest.main()
