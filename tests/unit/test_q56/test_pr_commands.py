"""Tests for Task 378 (/pr-create) and Task 379 (/pr-review)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_registry(llm_content="TITLE: My PR\nBODY:\nSummary here"):
    from lidco.cli.commands import CommandRegistry

    registry = CommandRegistry()
    session = MagicMock()
    llm_resp = MagicMock()
    llm_resp.content = llm_content
    session.llm.complete = AsyncMock(return_value=llm_resp)
    registry.set_session(session)
    return registry


def _invoke(handler, arg: str = "") -> str:
    return asyncio.run(handler(arg=arg))


def _mock_proc(returncode=0, stdout="", stderr=""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


class TestPrCreateCommand:
    def test_pr_create_registered(self):
        reg = _make_registry()
        assert reg.get("pr-create") is not None

    def test_pr_create_no_session(self):
        from lidco.cli.commands import CommandRegistry
        reg = CommandRegistry()
        reg._session = None
        cmd = reg.get("pr-create")
        result = _invoke(cmd.handler, "")
        assert "session" in result.lower() or "initialized" in result.lower()

    def test_pr_create_generates_title_and_body(self):
        reg = _make_registry("TITLE: Add feature\nBODY:\n## Summary\n- Added stuff")

        def _fake_run(args, **kwargs):
            if args[0] == "git":
                if "log" in args:
                    return _mock_proc(0, "abc123 feat: add feature")
                if "diff" in args:
                    return _mock_proc(0, "1 file changed")
                if "rev-parse" in args:
                    return _mock_proc(0, "feature/my-branch")
            if args[0] == "gh":
                return _mock_proc(0, "https://github.com/org/repo/pull/1")
            return _mock_proc(0, "")

        with patch("subprocess.run", side_effect=_fake_run):
            result = _invoke(reg.get("pr-create").handler, "")

        assert "Add feature" in result or "feature" in result.lower() or "PR" in result

    def test_pr_create_draft_flag(self):
        reg = _make_registry()

        def _fake_run(args, **kwargs):
            if args[0] == "gh" and "--draft" in args:
                return _mock_proc(0, "https://github.com/org/repo/pull/2")
            return _mock_proc(0, "")

        with patch("subprocess.run", side_effect=_fake_run):
            result = _invoke(reg.get("pr-create").handler, "--draft")

        # Should not error out
        assert result is not None

    def test_pr_create_llm_failure(self):
        from lidco.cli.commands import CommandRegistry
        reg = CommandRegistry()
        session = MagicMock()
        session.llm.complete = AsyncMock(side_effect=RuntimeError("LLM down"))
        reg.set_session(session)

        with patch("subprocess.run", return_value=_mock_proc(0, "")):
            result = _invoke(reg.get("pr-create").handler, "")

        assert "failed" in result.lower() or "error" in result.lower() or "LLM" in result


class TestPrReviewCommand:
    def test_pr_review_registered(self):
        reg = _make_registry()
        assert reg.get("pr-review") is not None

    def test_pr_review_no_args_shows_usage(self):
        reg = _make_registry()
        cmd = reg.get("pr-review")
        result = _invoke(cmd.handler, "")
        assert "Usage" in result or "pr-review" in result.lower()

    def test_pr_review_gh_not_found(self):
        reg = _make_registry()
        cmd = reg.get("pr-review")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _invoke(cmd.handler, "123")
        assert "not found" in result.lower() or "failed" in result.lower()

    def test_pr_review_gh_error(self):
        reg = _make_registry()
        cmd = reg.get("pr-review")
        with patch("subprocess.run", return_value=_mock_proc(1, "", "PR not found")):
            result = _invoke(cmd.handler, "999")
        assert "failed" in result.lower() or "error" in result.lower() or "999" in result

    def test_pr_review_returns_analysis(self):
        reg = _make_registry(
            "## Security\nNo issues found.\n\n## Code Quality\nLooks good.\n\n**APPROVE**"
        )
        cmd = reg.get("pr-review")

        diff = "diff --git a/foo.py b/foo.py\n+x = 1\n"
        with patch("subprocess.run", return_value=_mock_proc(0, diff)):
            result = _invoke(cmd.handler, "42")

        assert "42" in result
        assert "review" in result.lower() or "security" in result.lower() or "approve" in result.lower()

    def test_pr_review_empty_diff(self):
        reg = _make_registry()
        cmd = reg.get("pr-review")
        with patch("subprocess.run", return_value=_mock_proc(0, "")):
            result = _invoke(cmd.handler, "5")
        assert "empty" in result.lower() or "no diff" in result.lower()

    def test_pr_review_no_session(self):
        from lidco.cli.commands import CommandRegistry
        reg = CommandRegistry()
        reg._session = None
        cmd = reg.get("pr-review")
        with patch("subprocess.run", return_value=_mock_proc(0, "diff content")):
            result = _invoke(cmd.handler, "1")
        assert "session" in result.lower() or "initialized" in result.lower()
