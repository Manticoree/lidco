"""Tests for /bookmark (#188), /fmt (#189), /cost (#190)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


def _make_session_registry(**kwargs) -> CommandRegistry:
    reg = _make_registry()
    sess = MagicMock()
    tb = MagicMock()
    tb._total_tokens = kwargs.get("tokens", 1000)
    tb._total_prompt_tokens = kwargs.get("prompt", 700)
    tb._total_completion_tokens = kwargs.get("completion", 300)
    tb._total_cost_usd = kwargs.get("cost", 0.005)
    tb._by_role = kwargs.get("by_role", {})
    sess.token_budget = tb
    cfg = MagicMock()
    cfg.llm.default_model = kwargs.get("model", "gpt-4")
    sess.config = cfg
    reg.set_session(sess)
    return reg


# ── Task 188: /bookmark ───────────────────────────────────────────────────────

class TestBookmarkCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("bookmark") is not None

    def test_default_bookmarks_empty(self):
        reg = _make_registry()
        assert reg._bookmarks == {}

    def test_no_arg_shows_empty_message(self):
        reg = _make_registry()
        result = _run(reg.get("bookmark").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "закладок" in result.lower()

    def test_add_bookmark(self, tmp_path):
        f = tmp_path / "main.py"
        f.write_text("x = 1\n")
        reg = _make_registry()
        _run(reg.get("bookmark").handler(arg=f"add mymark {f}"))
        assert "mymark" in reg._bookmarks
        assert reg._bookmarks["mymark"]["file"] == str(f)

    def test_add_with_line_number(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def foo():\n    pass\n")
        reg = _make_registry()
        _run(reg.get("bookmark").handler(arg=f"add fn {f}:2"))
        assert reg._bookmarks["fn"]["line"] == 2

    def test_add_returns_confirmation(self, tmp_path):
        f = tmp_path / "f.py"
        f.write_text("a = 1")
        reg = _make_registry()
        result = _run(reg.get("bookmark").handler(arg=f"add bm {f}"))
        assert "bm" in result or "закладка" in result.lower()

    def test_add_nonexistent_file(self):
        reg = _make_registry()
        result = _run(reg.get("bookmark").handler(arg="add bm /nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_add_directory_rejected(self, tmp_path):
        reg = _make_registry()
        result = _run(reg.get("bookmark").handler(arg=f"add bm {tmp_path}"))
        assert "не файл" in result or "not a file" in result.lower()

    def test_list_shows_bookmarks(self, tmp_path):
        f = tmp_path / "x.py"
        f.write_text("x")
        reg = _make_registry()
        reg._bookmarks["alpha"] = {"file": str(f), "line": None}
        result = _run(reg.get("bookmark").handler(arg="list"))
        assert "alpha" in result
        assert str(f) in result

    def test_del_removes_bookmark(self, tmp_path):
        f = tmp_path / "y.py"
        f.write_text("y")
        reg = _make_registry()
        reg._bookmarks["old"] = {"file": str(f), "line": None}
        _run(reg.get("bookmark").handler(arg="del old"))
        assert "old" not in reg._bookmarks

    def test_del_nonexistent_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("bookmark").handler(arg="del ghost"))
        assert "не найдена" in result or "not found" in result.lower()

    def test_clear_removes_all(self, tmp_path):
        f = tmp_path / "z.py"
        f.write_text("z")
        reg = _make_registry()
        reg._bookmarks = {
            "a": {"file": str(f), "line": None},
            "b": {"file": str(f), "line": 1},
        }
        _run(reg.get("bookmark").handler(arg="clear"))
        assert reg._bookmarks == {}

    def test_go_shows_file_content(self, tmp_path):
        f = tmp_path / "view.py"
        f.write_text("def hello():\n    return 42\n")
        reg = _make_registry()
        reg._bookmarks["fn"] = {"file": str(f), "line": None}
        result = _run(reg.get("bookmark").handler(arg="go fn"))
        assert "hello" in result or "42" in result

    def test_go_with_line_shows_context(self, tmp_path):
        lines = [f"line_{i} = {i}" for i in range(20)]
        f = tmp_path / "lines.py"
        f.write_text("\n".join(lines) + "\n")
        reg = _make_registry()
        reg._bookmarks["here"] = {"file": str(f), "line": 10}
        result = _run(reg.get("bookmark").handler(arg="go here"))
        assert "10" in result
        assert "→" in result  # marked line

    def test_go_nonexistent_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("bookmark").handler(arg="go ghost"))
        assert "не найдена" in result or "not found" in result.lower()

    def test_go_shows_available_when_not_found(self):
        reg = _make_registry()
        reg._bookmarks["v1"] = {"file": "x.py", "line": None}
        result = _run(reg.get("bookmark").handler(arg="go ghost"))
        assert "v1" in result


# ── Task 189: /fmt ────────────────────────────────────────────────────────────

class TestFmtCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("fmt") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("fmt").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_path_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("fmt").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_successful_format(self, tmp_path):
        f = tmp_path / "ugly.py"
        f.write_text("x=1\n")
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"1 file reformatted", b""))
            mock_exec.return_value = proc
            reg = _make_registry()
            result = _run(reg.get("fmt").handler(arg=str(f)))
        # Ran without crash
        assert isinstance(result, str)

    def test_check_mode_no_changes_needed(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("x = 1\n")
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = proc
            reg = _make_registry()
            result = _run(reg.get("fmt").handler(arg=f"{f} --check"))
        assert "✓" in result or "не требуется" in result

    def test_check_mode_changes_needed(self, tmp_path):
        f = tmp_path / "ugly2.py"
        f.write_text("x=1\n")
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.returncode = 1
            proc.communicate = AsyncMock(return_value=(b"", b"Would reformat ugly2.py"))
            mock_exec.return_value = proc
            reg = _make_registry()
            result = _run(reg.get("fmt").handler(arg=f"{f} --check"))
        assert "✗" in result or "требуется" in result

    def test_ruff_not_found_shows_hint(self, tmp_path):
        f = tmp_path / "x.py"
        f.write_text("x = 1\n")
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            reg = _make_registry()
            result = _run(reg.get("fmt").handler(arg=str(f)))
        assert "ruff" in result.lower() or "не найден" in result.lower()

    def test_timeout_shows_error(self, tmp_path):
        f = tmp_path / "slow.py"
        f.write_text("x = 1\n")
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_exec.return_value = proc
            reg = _make_registry()
            result = _run(reg.get("fmt").handler(arg=str(f)))
        assert "время" in result.lower() or "timeout" in result.lower() or "превысил" in result.lower()


# ── Task 190: /cost ───────────────────────────────────────────────────────────

class TestCostCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("cost") is not None

    def test_no_session_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("cost").handler())
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_shows_model(self):
        reg = _make_session_registry(model="anthropic/claude-opus-4")
        result = _run(reg.get("cost").handler())
        assert "claude-opus-4" in result

    def test_shows_token_counts(self):
        reg = _make_session_registry(tokens=2000, prompt=1400, completion=600)
        result = _run(reg.get("cost").handler())
        assert "1400" in result or "1.4k" in result
        assert "600" in result
        assert "2000" in result or "2.0k" in result

    def test_shows_cost(self):
        reg = _make_session_registry(cost=0.01234)
        result = _run(reg.get("cost").handler())
        assert "0.01234" in result or "$" in result

    def test_zero_cost_displayed(self):
        reg = _make_session_registry(cost=0.0)
        result = _run(reg.get("cost").handler())
        assert "$" in result or "стоимость" in result.lower()

    def test_shows_per_agent_breakdown(self):
        reg = _make_session_registry(
            tokens=1000,
            cost=0.005,
            by_role={"coder": 700, "tester": 300},
        )
        result = _run(reg.get("cost").handler())
        assert "coder" in result
        assert "tester" in result

    def test_shows_percentages(self):
        reg = _make_session_registry(
            tokens=1000,
            by_role={"coder": 700, "tester": 300},
        )
        result = _run(reg.get("cost").handler())
        assert "70%" in result
        assert "30%" in result

    def test_shows_turn_timing(self):
        reg = _make_session_registry()
        reg._turn_times = [2.0, 3.0, 1.5]
        result = _run(reg.get("cost").handler())
        assert "3" in result  # 3 turns
        assert "6.5" in result or "2.2" in result  # total or avg

    def test_shows_navigation_hints(self):
        reg = _make_session_registry()
        result = _run(reg.get("cost").handler())
        assert "/budget" in result or "/profile" in result or "/timing" in result

    def test_no_by_role_still_works(self):
        reg = _make_session_registry(by_role={})
        result = _run(reg.get("cost").handler())
        assert "стоимость" in result.lower() or "cost" in result.lower() or "$" in result
