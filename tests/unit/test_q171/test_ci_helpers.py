"""Tests for CI/CD helpers — Q171 task 970."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from lidco.api.ci_helpers import (
    CIEnvironment,
    detect_ci,
    exit_code,
    format_ci_output,
    github_pr_comment,
    gitlab_mr_note,
)
from lidco.api.library import LidcoResult


class TestCIEnvironment(unittest.TestCase):
    def test_fields(self):
        env = CIEnvironment(provider="github", branch="main", commit="abc123", pr_number=42, repo="org/repo")
        self.assertEqual(env.provider, "github")
        self.assertEqual(env.pr_number, 42)


class TestDetectCI(unittest.TestCase):
    @patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_REF_NAME": "feat", "GITHUB_SHA": "abc", "GITHUB_REPOSITORY": "o/r"}, clear=False)
    def test_github(self):
        env = detect_ci()
        self.assertEqual(env.provider, "github")
        self.assertEqual(env.branch, "feat")
        self.assertEqual(env.commit, "abc")
        self.assertEqual(env.repo, "o/r")

    @patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_PR_NUMBER": "7"}, clear=False)
    def test_github_pr(self):
        env = detect_ci()
        self.assertEqual(env.pr_number, 7)

    @patch.dict(os.environ, {"GITLAB_CI": "true", "CI_COMMIT_BRANCH": "dev", "CI_COMMIT_SHA": "def", "CI_PROJECT_PATH": "g/p"}, clear=False)
    def test_gitlab(self):
        # Remove github keys if present
        with patch.dict(os.environ, {"GITHUB_ACTIONS": ""}, clear=False):
            env = detect_ci()
            self.assertEqual(env.provider, "gitlab")
            self.assertEqual(env.branch, "dev")

    def test_local(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "", "GITLAB_CI": ""}, clear=False):
            env = detect_ci()
            self.assertEqual(env.provider, "local")


class TestFormatCIOutput(unittest.TestCase):
    def test_success(self):
        r = LidcoResult(success=True, output="ok", tokens_used=10, duration=1.23)
        env = CIEnvironment(provider="github", branch="main", commit="abc12345", pr_number=None, repo="o/r")
        out = format_ci_output(r, env)
        self.assertIn("PASS", out)
        self.assertIn("main", out)
        self.assertIn("abc12345", out)

    def test_failure_with_error(self):
        r = LidcoResult(success=False, output="", error="oops", duration=0.5)
        env = CIEnvironment(provider="local", branch="", commit="", pr_number=None, repo="")
        out = format_ci_output(r, env)
        self.assertIn("FAIL", out)
        self.assertIn("oops", out)

    def test_files_changed(self):
        r = LidcoResult(success=True, output="ok", files_changed=["a.py", "b.py"])
        env = CIEnvironment(provider="github", branch="x", commit="y", pr_number=None, repo="")
        out = format_ci_output(r, env)
        self.assertIn("a.py", out)


class TestGithubPrComment(unittest.TestCase):
    def test_success_md(self):
        r = LidcoResult(success=True, output="done", tokens_used=5, duration=0.1, files_changed=["x.py"])
        md = github_pr_comment(r)
        self.assertIn("Success", md)
        self.assertIn("x.py", md)
        self.assertIn("```", md)

    def test_failure_md(self):
        r = LidcoResult(success=False, output="", error="err")
        md = github_pr_comment(r)
        self.assertIn("Failure", md)
        self.assertIn("err", md)


class TestGitlabMrNote(unittest.TestCase):
    def test_success(self):
        r = LidcoResult(success=True, output="ok", tokens_used=3, duration=0.5)
        md = gitlab_mr_note(r)
        self.assertIn("Success", md)
        self.assertIn("| Tokens |", md)

    def test_with_files(self):
        r = LidcoResult(success=True, output="ok", files_changed=["f.py"])
        md = gitlab_mr_note(r)
        self.assertIn("f.py", md)


class TestExitCode(unittest.TestCase):
    def test_success(self):
        self.assertEqual(exit_code(LidcoResult(success=True, output="")), 0)

    def test_failure(self):
        self.assertEqual(exit_code(LidcoResult(success=False, output="")), 1)


if __name__ == "__main__":
    unittest.main()
