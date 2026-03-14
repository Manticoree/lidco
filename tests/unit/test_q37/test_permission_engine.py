"""Tests for PermissionEngine — Q37 task 245/246."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lidco.core.config import PermissionsConfig
from lidco.core.permission_engine import (
    PermissionEngine,
    PermissionMode,
    ParsedRule,
    RuleMatcher,
    RuleParser,
)


# ─── RuleParser ──────────────────────────────────────────────────────────────


class TestRuleParser:
    def test_plain_tool_name(self) -> None:
        r = RuleParser.parse("Bash")
        assert r.tool_name == "Bash"
        assert r.pattern == "**"

    def test_tool_with_pattern(self) -> None:
        r = RuleParser.parse("Bash(pytest *)")
        assert r.tool_name == "Bash"
        assert r.pattern == "pytest *"

    def test_file_rule(self) -> None:
        r = RuleParser.parse("FileWrite(.env)")
        assert r.tool_name == "FileWrite"
        assert r.pattern == ".env"

    def test_raw_preserved(self) -> None:
        spec = "Bash(git push *)"
        r = RuleParser.parse(spec)
        assert r.raw == spec

    def test_whitespace_stripped(self) -> None:
        r = RuleParser.parse("  Bash(  pytest  )  ")
        assert r.tool_name == "Bash"
        assert r.pattern == "pytest"


# ─── RuleMatcher ─────────────────────────────────────────────────────────────


class TestRuleMatcher:
    def _rule(self, spec: str) -> ParsedRule:
        return RuleParser.parse(spec)

    # Bash matching
    def test_bash_wildcard_all(self) -> None:
        rule = self._rule("Bash(**)")
        assert RuleMatcher.matches(rule, "bash", {"command": "anything goes"})

    def test_bash_prefix_wildcard(self) -> None:
        rule = self._rule("Bash(pytest *)")
        assert RuleMatcher.matches(rule, "bash", {"command": "pytest -q tests/"})
        assert not RuleMatcher.matches(rule, "bash", {"command": "git push origin main"})

    def test_bash_exact_prefix(self) -> None:
        rule = self._rule("Bash(git push *)")
        assert RuleMatcher.matches(rule, "bash", {"command": "git push origin main"})
        assert not RuleMatcher.matches(rule, "bash", {"command": "git status"})

    def test_bash_plain_tool(self) -> None:
        rule = self._rule("Bash")
        assert RuleMatcher.matches(rule, "bash", {"command": "anything"})

    # File path matching
    def test_file_write_exact(self) -> None:
        rule = self._rule("FileWrite(.env)")
        assert RuleMatcher.matches(rule, "file_write", {"path": ".env"})
        assert not RuleMatcher.matches(rule, "file_write", {"path": "src/foo.py"})

    def test_file_write_glob(self) -> None:
        rule = self._rule("FileWrite(src/**)")
        assert RuleMatcher.matches(rule, "file_write", {"path": "src/lidco/core/foo.py"})
        assert not RuleMatcher.matches(rule, "file_write", {"path": "tests/foo.py"})

    # Tool name mismatch
    def test_tool_mismatch(self) -> None:
        rule = self._rule("Bash(pytest *)")
        assert not RuleMatcher.matches(rule, "file_write", {"command": "pytest"})

    # Case insensitivity for tool name
    def test_tool_name_case_insensitive(self) -> None:
        rule = self._rule("BASH(pytest *)")
        assert RuleMatcher.matches(rule, "bash", {"command": "pytest -q"})


# ─── PermissionEngine ────────────────────────────────────────────────────────


def _make_engine(
    mode: str = "default",
    allow: list[str] | None = None,
    ask: list[str] | None = None,
    deny: list[str] | None = None,
) -> PermissionEngine:
    config = PermissionsConfig(
        mode=mode,
        allow_rules=allow or [],
        ask_rules=ask or [],
        deny_rules=deny or [],
        command_allowlist=[],  # disable defaults for isolation
    )
    return PermissionEngine(config)


class TestPermissionEngineBasic:
    def test_bypass_allows_everything(self) -> None:
        engine = _make_engine(mode="bypass")
        result = engine.check("bash", {"command": "rm -rf /"})
        assert result.decision == "allow"

    def test_deny_rule_takes_precedence(self) -> None:
        engine = _make_engine(
            deny=["Bash(git push *)"],
            allow=["Bash(git *)"],
        )
        result = engine.check("bash", {"command": "git push origin main"})
        assert result.decision == "deny"

    def test_allow_rule_before_ask(self) -> None:
        engine = _make_engine(
            allow=["Bash(pytest *)"],
            ask=["Bash(*)"],
        )
        result = engine.check("bash", {"command": "pytest -q"})
        assert result.decision == "allow"

    def test_ask_rule_matched(self) -> None:
        engine = _make_engine(ask=["Bash(git *)"])
        result = engine.check("bash", {"command": "git status"})
        assert result.decision == "ask"

    def test_default_ask_for_bash(self) -> None:
        engine = _make_engine()
        result = engine.check("bash", {"command": "echo hello"})
        assert result.decision == "ask"

    def test_read_only_tools_always_allowed(self) -> None:
        engine = _make_engine()
        for tool in ("file_read", "glob", "grep", "web_search"):
            r = engine.check(tool, {})
            assert r.decision == "allow", f"{tool} should be auto-allowed"


class TestPermissionModes:
    def test_plan_mode_blocks_bash(self) -> None:
        engine = _make_engine(mode="plan")
        result = engine.check("bash", {"command": "echo hello"})
        assert result.decision == "deny"

    def test_plan_mode_blocks_file_write(self) -> None:
        engine = _make_engine(mode="plan")
        result = engine.check("file_write", {"path": "foo.py"})
        assert result.decision == "deny"

    def test_plan_mode_allows_file_read(self) -> None:
        engine = _make_engine(mode="plan")
        result = engine.check("file_read", {"path": "foo.py"})
        assert result.decision == "allow"

    def test_accept_edits_allows_file_edit(self) -> None:
        engine = _make_engine(mode="accept_edits")
        result = engine.check("file_edit", {"path": "foo.py"})
        assert result.decision == "allow"

    def test_accept_edits_asks_for_bash(self) -> None:
        engine = _make_engine(mode="accept_edits")
        result = engine.check("bash", {"command": "echo hello"})
        assert result.decision == "ask"

    def test_dont_ask_denies_unmatched(self) -> None:
        engine = _make_engine(mode="dont_ask")
        result = engine.check("bash", {"command": "echo hello"})
        assert result.decision == "deny"

    def test_dont_ask_allows_explicit_rule(self) -> None:
        engine = _make_engine(mode="dont_ask", allow=["Bash(echo *)"])
        result = engine.check("bash", {"command": "echo hello"})
        assert result.decision == "allow"


class TestPermissionEngineSessionDecisions:
    def test_session_allow_remembered(self) -> None:
        engine = _make_engine()
        engine.add_session_allow("bash", {"command": "pytest -q"})
        result = engine.check("bash", {"command": "pytest -q"})
        assert result.decision == "allow"

    def test_session_deny_remembered(self) -> None:
        engine = _make_engine()
        engine.add_session_deny("bash", {"command": "pytest -q"})
        result = engine.check("bash", {"command": "pytest -q"})
        assert result.decision == "deny"

    def test_session_deny_beats_allow_rule(self) -> None:
        engine = _make_engine(allow=["Bash(pytest *)"])
        engine.add_session_deny("bash", {"command": "pytest -q"})
        result = engine.check("bash", {"command": "pytest -q"})
        assert result.decision == "deny"

    def test_set_mode_runtime(self) -> None:
        engine = _make_engine(mode="default")
        engine.set_mode("bypass")
        assert engine.mode == PermissionMode.BYPASS
        result = engine.check("bash", {"command": "dangerous"})
        assert result.decision == "allow"


class TestPermissionEnginePersistent:
    def test_persistent_allow_saved_and_loaded(self, tmp_path: Path) -> None:
        perm_file = tmp_path / "permissions.json"
        engine = _make_engine()
        engine.load_persistent(perm_file)
        engine.add_persistent_allow("Bash(pytest *)")

        assert perm_file.exists()
        data = json.loads(perm_file.read_text())
        assert "Bash(pytest *)" in data["allow"]

        # Reload
        engine2 = _make_engine()
        engine2.load_persistent(perm_file)
        result = engine2.check("bash", {"command": "pytest -q"})
        assert result.decision == "allow"

    def test_persistent_deny_saved(self, tmp_path: Path) -> None:
        perm_file = tmp_path / "permissions.json"
        engine = _make_engine()
        engine.load_persistent(perm_file)
        engine.add_persistent_deny("Bash(git push *)")

        engine2 = _make_engine()
        engine2.load_persistent(perm_file)
        result = engine2.check("bash", {"command": "git push origin main"})
        assert result.decision == "deny"

    def test_corrupt_file_silently_ignored(self, tmp_path: Path) -> None:
        perm_file = tmp_path / "permissions.json"
        perm_file.write_text("not valid json", encoding="utf-8")
        engine = _make_engine()
        engine.load_persistent(perm_file)  # should not raise
        result = engine.check("bash", {"command": "echo hello"})
        assert result.decision in ("allow", "ask")


class TestPermissionEngineSummary:
    def test_summary_contains_mode(self) -> None:
        engine = _make_engine(mode="plan")
        summary = engine.get_summary()
        assert summary["mode"] == "plan"

    def test_summary_contains_rules(self) -> None:
        engine = _make_engine(
            allow=["Bash(pytest *)"],
            deny=["Bash(git push *)"],
        )
        summary = engine.get_summary()
        assert "Bash(pytest *)" in summary["allow_rules"]
        assert "Bash(git push *)" in summary["deny_rules"]


class TestPermissionEngineBackwardCompat:
    def test_legacy_auto_allow(self) -> None:
        config = PermissionsConfig(auto_allow=["file_read"])
        engine = PermissionEngine(config)
        result = engine.check("file_read", {})
        assert result.decision == "allow"

    def test_legacy_deny(self) -> None:
        config = PermissionsConfig(deny=["bash"])
        engine = PermissionEngine(config)
        result = engine.check("bash", {"command": "echo"})
        assert result.decision == "deny"
