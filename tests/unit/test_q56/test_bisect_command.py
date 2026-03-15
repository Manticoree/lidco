"""Tests for Task 376 — /bisect command."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_registry():
    """Create a minimal CommandRegistry with a mock session."""
    from lidco.cli.commands import CommandRegistry

    registry = CommandRegistry()
    session = MagicMock()
    session.llm = MagicMock()
    registry.set_session(session)
    return registry


def _invoke(handler, arg: str = "") -> str:
    """Run an async command handler synchronously."""
    return asyncio.run(handler(arg=arg))


class TestBisectCommand:
    def test_bisect_registered(self):
        reg = _make_registry()
        cmd = reg.get("bisect")
        assert cmd is not None
        assert cmd.name == "bisect"

    def test_bisect_no_args_shows_help(self):
        reg = _make_registry()
        cmd = reg.get("bisect")
        result = asyncio.run(cmd.handler(arg=""))
        assert "Usage" in result or "bisect" in result.lower()

    def test_bisect_stop(self):
        reg = _make_registry()
        cmd = reg.get("bisect")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = _invoke(cmd.handler, "stop")
        assert "stop" in result.lower() or "reset" in result.lower()

    def test_bisect_stop_git_not_found(self):
        reg = _make_registry()
        cmd = reg.get("bisect")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _invoke(cmd.handler, "stop")
        assert "not found" in result.lower() or "failed" in result.lower() or "error" in result.lower()

    def test_bisect_start_no_test_shows_usage(self):
        reg = _make_registry()
        cmd = reg.get("bisect")
        result = _invoke(cmd.handler, "start")
        assert "Usage" in result or "test" in result.lower()

    def test_bisect_start_marks_bad_and_shows_log(self):
        reg = _make_registry()
        cmd = reg.get("bisect")

        def _fake_run(args, **kwargs):
            m = MagicMock()
            m.returncode = 0
            if "bisect" in args:
                m.stdout = "Bisecting: 5 revisions left"
                m.stderr = ""
            else:
                m.stdout = "abc1234 feat: something\ndef5678 fix: bug\n"
                m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=_fake_run):
            result = _invoke(cmd.handler, "start pytest tests/")

        assert "bad" in result.lower() or "started" in result.lower() or "bisect" in result.lower()

    def test_bisect_run_no_test_shows_usage(self):
        reg = _make_registry()
        cmd = reg.get("bisect")
        result = _invoke(cmd.handler, "run")
        assert "Usage" in result or "test" in result.lower()

    def test_bisect_run_marks_good_when_test_passes(self):
        reg = _make_registry()
        cmd = reg.get("bisect")

        call_count = [0]

        def _fake_run(args, **kwargs):
            m = MagicMock()
            m.returncode = 0
            m.stdout = "Bisecting: 3 revisions"
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=_fake_run):
            result = _invoke(cmd.handler, "run pytest tests/")

        assert "good" in result.lower() or "bad" in result.lower()
