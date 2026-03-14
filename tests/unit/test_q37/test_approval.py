"""Tests for approval.py — Q37 task 247."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lidco.cli.approval import (
    Decision,
    _CHOICES,
    _TOOL_EXPLANATIONS,
    ask,
)
from lidco.core.permission_engine import PermissionResult


# ─── Decision enum ────────────────────────────────────────────────────────────


class TestDecisionEnum:
    def test_all_values(self) -> None:
        values = {d.value for d in Decision}
        assert values == {
            "allow_once",
            "allow_session",
            "allow_always",
            "deny_once",
            "deny_always",
            "explain",
        }

    def test_str_mixin(self) -> None:
        assert Decision.ALLOW_ONCE == "allow_once"
        assert Decision.DENY_ALWAYS == "deny_always"


# ─── _CHOICES structure ───────────────────────────────────────────────────────


class TestChoices:
    def test_all_six_choices_present(self) -> None:
        assert len(_CHOICES) == 6

    def test_keys_unique(self) -> None:
        keys = [c.key for c in _CHOICES]
        assert len(keys) == len(set(keys))

    def test_decisions_cover_all(self) -> None:
        decisions = {c.decision for c in _CHOICES}
        assert Decision.ALLOW_ONCE in decisions
        assert Decision.DENY_ALWAYS in decisions
        assert Decision.EXPLAIN in decisions

    def test_allow_once_key_is_y(self) -> None:
        allow_once = next(c for c in _CHOICES if c.decision == Decision.ALLOW_ONCE)
        assert allow_once.key == "y"

    def test_deny_once_key_is_n(self) -> None:
        deny_once = next(c for c in _CHOICES if c.decision == Decision.DENY_ONCE)
        assert deny_once.key == "n"

    def test_explain_key_is_e(self) -> None:
        explain = next(c for c in _CHOICES if c.decision == Decision.EXPLAIN)
        assert explain.key == "e"


# ─── _TOOL_EXPLANATIONS ───────────────────────────────────────────────────────


class TestToolExplanations:
    def test_bash_has_explanation(self) -> None:
        assert "bash" in _TOOL_EXPLANATIONS
        assert len(_TOOL_EXPLANATIONS["bash"]) > 10

    def test_file_write_has_explanation(self) -> None:
        assert "file_write" in _TOOL_EXPLANATIONS

    def test_git_has_explanation(self) -> None:
        assert "git" in _TOOL_EXPLANATIONS


# ─── ask() function ───────────────────────────────────────────────────────────


class TestAskFunction:
    def _make_result(self, risk: str = "yellow") -> PermissionResult:
        return PermissionResult("ask", "default", risk=risk)

    def _make_console(self):
        from rich.console import Console
        return Console(quiet=True)

    def test_returns_allow_once(self) -> None:
        result = self._make_result()
        with patch("lidco.cli.approval._run_prompt", return_value=Decision.ALLOW_ONCE):
            decision = ask("bash", {"command": "ls"}, result, self._make_console())
        assert decision == Decision.ALLOW_ONCE

    def test_returns_deny_once(self) -> None:
        result = self._make_result()
        with patch("lidco.cli.approval._run_prompt", return_value=Decision.DENY_ONCE):
            decision = ask("bash", {"command": "rm -rf /tmp/x"}, result, self._make_console())
        assert decision == Decision.DENY_ONCE

    def test_returns_allow_session(self) -> None:
        result = self._make_result()
        with patch("lidco.cli.approval._run_prompt", return_value=Decision.ALLOW_SESSION):
            decision = ask("file_write", {"path": "foo.py"}, result, self._make_console())
        assert decision == Decision.ALLOW_SESSION

    def test_returns_deny_always(self) -> None:
        result = self._make_result()
        with patch("lidco.cli.approval._run_prompt", return_value=Decision.DENY_ALWAYS):
            decision = ask("bash", {}, result, self._make_console())
        assert decision == Decision.DENY_ALWAYS

    def test_explain_loops_then_allow(self) -> None:
        """EXPLAIN should re-prompt; second call returns ALLOW_ONCE."""
        result = self._make_result()
        side_effects = [Decision.EXPLAIN, Decision.ALLOW_ONCE]
        console = self._make_console()
        with patch("lidco.cli.approval._run_prompt", side_effect=side_effects):
            decision = ask("bash", {"command": "pytest"}, result, console)
        assert decision == Decision.ALLOW_ONCE

    def test_explain_shows_known_tool_explanation(self) -> None:
        """EXPLAIN for 'bash' prints non-empty explanation text."""
        result = self._make_result()
        printed: list[str] = []
        side_effects = [Decision.EXPLAIN, Decision.DENY_ONCE]

        from rich.console import Console
        real_console = Console(quiet=True)

        original_print = real_console.print

        def capture_print(*args, **kwargs):
            printed.append(str(args))
            original_print(*args, **kwargs)

        real_console.print = capture_print  # type: ignore[method-assign]

        with patch("lidco.cli.approval._run_prompt", side_effect=side_effects):
            ask("bash", {}, result, real_console)

        assert any("bash" in p.lower() or "shell" in p.lower() for p in printed)

    def test_explain_unknown_tool_uses_fallback(self) -> None:
        """EXPLAIN for unknown tool uses generic description."""
        result = self._make_result()
        console = self._make_console()
        side_effects = [Decision.EXPLAIN, Decision.ALLOW_ONCE]
        with patch("lidco.cli.approval._run_prompt", side_effect=side_effects):
            decision = ask("unknown_tool_xyz", {}, result, console)
        assert decision == Decision.ALLOW_ONCE

    def test_multiple_explain_then_deny(self) -> None:
        """Multiple EXPLAIN cycles before final decision."""
        result = self._make_result()
        console = self._make_console()
        side_effects = [Decision.EXPLAIN, Decision.EXPLAIN, Decision.DENY_ALWAYS]
        with patch("lidco.cli.approval._run_prompt", side_effect=side_effects):
            decision = ask("git", {"args": "push"}, result, console)
        assert decision == Decision.DENY_ALWAYS

    def test_allow_always(self) -> None:
        result = self._make_result()
        with patch("lidco.cli.approval._run_prompt", return_value=Decision.ALLOW_ALWAYS):
            decision = ask("file_write", {"path": "x.py"}, result, self._make_console())
        assert decision == Decision.ALLOW_ALWAYS

    def test_red_risk_tool(self) -> None:
        result = PermissionResult("ask", "dangerous", risk="red")
        with patch("lidco.cli.approval._run_prompt", return_value=Decision.DENY_ONCE):
            decision = ask("bash", {"command": "rm -rf /"}, result, self._make_console())
        assert decision == Decision.DENY_ONCE
