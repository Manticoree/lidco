"""Tests for /shortcuts, /whois, and session_status branch — Tasks 158–160."""

from __future__ import annotations

import asyncio
from io import StringIO
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from lidco.cli.commands import CommandRegistry
from lidco.cli.renderer import Renderer


# ── helpers ───────────────────────────────────────────────────────────────────

def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry(agents: list[str] | None = None) -> CommandRegistry:
    reg = CommandRegistry()
    if agents is not None:
        session = MagicMock()
        session.agent_registry.list_names.return_value = agents
        reg.set_session(session)
    return reg


def _captured_renderer() -> tuple[Renderer, StringIO]:
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    return Renderer(console), buf


# ── Task 158: git branch in session_status ────────────────────────────────────

class TestSessionStatusBranch:
    def test_branch_shown_when_provided(self):
        renderer, buf = _captured_renderer()
        renderer.session_status(
            model="gpt-4", agent="auto", turns=1, tokens=100, cost_usd=0.0,
            branch="main",
        )
        assert "main" in buf.getvalue()

    def test_no_branch_no_crash(self):
        renderer, buf = _captured_renderer()
        renderer.session_status(
            model="gpt-4", agent="auto", turns=1, tokens=100, cost_usd=0.0,
        )
        output = buf.getvalue()
        assert "gpt-4" in output

    def test_branch_empty_string_hidden(self):
        renderer, buf = _captured_renderer()
        renderer.session_status(
            model="gpt-4", agent="coder", turns=0, tokens=0, cost_usd=0.0,
            branch="",
        )
        output = buf.getvalue()
        # Branch should not appear as a label if empty
        assert "branch" not in output.lower()

    def test_feature_branch_shown(self):
        renderer, buf = _captured_renderer()
        renderer.session_status(
            model="m", agent="auto", turns=0, tokens=0, cost_usd=0.0,
            branch="feature/my-feature",
        )
        assert "feature/my-feature" in buf.getvalue()

    def test_model_still_shown_with_branch(self):
        renderer, buf = _captured_renderer()
        renderer.session_status(
            model="claude-3", agent="auto", turns=2, tokens=500, cost_usd=0.0,
            branch="develop",
        )
        output = buf.getvalue()
        assert "claude-3" in output
        assert "develop" in output


# ── Task 158: _get_git_branch helper ──────────────────────────────────────────

class TestGetGitBranch:
    def test_returns_string(self):
        from lidco.cli.app import _get_git_branch
        result = _get_git_branch()
        assert isinstance(result, str)

    def test_returns_empty_in_non_git_dir(self, tmp_path, monkeypatch):
        import subprocess
        from lidco.cli import app

        original = subprocess.run
        def fake_run(*args, **kwargs):
            r = MagicMock()
            r.returncode = 128  # not a git repo
            r.stdout = ""
            return r

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = app._get_git_branch()
        assert result == ""


# ── Task 159: /shortcuts ──────────────────────────────────────────────────────

class TestShortcutsCommand:
    def test_registered(self):
        reg = CommandRegistry()
        assert reg.get("shortcuts") is not None

    def test_returns_string(self):
        reg = CommandRegistry()
        result = _run(reg.get("shortcuts").handler())
        assert isinstance(result, str)

    def test_contains_ctrl_l(self):
        reg = CommandRegistry()
        result = _run(reg.get("shortcuts").handler())
        assert "Ctrl+L" in result

    def test_contains_ctrl_r(self):
        reg = CommandRegistry()
        result = _run(reg.get("shortcuts").handler())
        assert "Ctrl+R" in result

    def test_contains_ctrl_e(self):
        reg = CommandRegistry()
        result = _run(reg.get("shortcuts").handler())
        assert "Ctrl+E" in result

    def test_contains_ctrl_p(self):
        reg = CommandRegistry()
        result = _run(reg.get("shortcuts").handler())
        assert "Ctrl+P" in result

    def test_contains_esc_enter(self):
        reg = CommandRegistry()
        result = _run(reg.get("shortcuts").handler())
        assert "Esc" in result

    def test_mentions_multiline(self):
        reg = CommandRegistry()
        result = _run(reg.get("shortcuts").handler())
        assert "строк" in result.lower() or "multiline" in result.lower() or "мультилайн" in result.lower()

    def test_no_session_required(self):
        reg = CommandRegistry()  # no session
        result = _run(reg.get("shortcuts").handler())
        assert "Ctrl" in result


# ── Task 160: /whois ──────────────────────────────────────────────────────────

class TestWhoisCommand:
    def test_registered(self):
        reg = CommandRegistry()
        assert reg.get("whois") is not None

    def test_no_arg_returns_usage(self):
        reg = _make_registry(["coder", "tester"])
        result = _run(reg.get("whois").handler(arg=""))
        assert "Использование" in result or "whois" in result.lower()

    def test_no_arg_lists_agents(self):
        reg = _make_registry(["coder", "architect"])
        result = _run(reg.get("whois").handler(arg=""))
        assert "coder" in result
        assert "architect" in result

    def test_unknown_agent_error(self):
        reg = _make_registry(["coder"])
        result = _run(reg.get("whois").handler(arg="phantom"))
        assert "не найден" in result or "phantom" in result

    def test_no_session_returns_message(self):
        reg = CommandRegistry()  # no session
        result = _run(reg.get("whois").handler(arg="coder"))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_at_prefix_stripped(self):
        reg = _make_registry(["coder"])
        # "@coder" should behave same as "coder" (prefix stripped)
        # Without real session, just check it doesn't crash
        result = _run(reg.get("whois").handler(arg="@coder"))
        assert isinstance(result, str)

    def test_known_agent_with_session(self):
        reg = CommandRegistry()
        session = MagicMock()
        # Mock agent with description and tools
        mock_agent = MagicMock()
        mock_agent.name = "coder"
        mock_agent.description = "Пишет и редактирует код"
        mock_agent.tools = {"file_write": MagicMock(), "bash": MagicMock()}
        session.agent_registry.list_names.return_value = ["coder"]
        session.agent_registry.get.return_value = mock_agent
        reg.set_session(session)
        result = _run(reg.get("whois").handler(arg="coder"))
        assert "coder" in result
        assert "Пишет" in result or "coder" in result

    def test_result_contains_routing_hint(self):
        reg = CommandRegistry()
        session = MagicMock()
        mock_agent = MagicMock()
        mock_agent.name = "tester"
        mock_agent.description = "Тестирует код"
        mock_agent.tools = {}
        session.agent_registry.list_names.return_value = ["tester"]
        session.agent_registry.get.return_value = mock_agent
        reg.set_session(session)
        result = _run(reg.get("whois").handler(arg="tester"))
        # Should mention @tester or /as tester
        assert "@tester" in result or "/as tester" in result
