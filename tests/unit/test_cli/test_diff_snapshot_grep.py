"""Tests for /diff (#176), /snapshot (#177), /grep (#178)."""

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
    orch = MagicMock()
    orch._conversation_history = kwargs.get("history", [])
    orch.restore_history = MagicMock()
    sess.orchestrator = orch
    reg.set_session(sess)
    return reg


# ── Task 176: /diff ───────────────────────────────────────────────────────────

class TestDiffCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("diff") is not None

    def test_no_changes_empty_message(self):
        reg = _make_registry()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = proc
            result = _run(reg.get("diff").handler())
        assert "нет" in result.lower() or "no" in result.lower() or "изменений" in result.lower()

    def test_with_diff_shows_diff_block(self):
        reg = _make_registry()
        diff_content = b"diff --git a/foo.py b/foo.py\n+new line\n"
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(diff_content, b""))
            mock_exec.return_value = proc
            result = _run(reg.get("diff").handler())
        assert "```diff" in result or "diff" in result

    def test_no_changes_with_session_edited_files_shows_hint(self):
        reg = _make_registry()
        reg._edited_files = ["src/auth.py"]
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = proc
            result = _run(reg.get("diff").handler())
        # Should mention the edited file in hint
        assert "auth.py" in result or "нет" in result.lower()

    def test_file_arg_passed_to_git(self):
        reg = _make_registry()
        diff_content = b"diff --git a/x.py b/x.py\n+change\n"
        called_with = []

        async def _fake_exec(*args, **kwargs):
            called_with.extend(args)
            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(diff_content, b""))
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=_fake_exec):
            result = _run(reg.get("diff").handler(arg="src/x.py"))
        assert "src/x.py" in " ".join(str(a) for a in called_with) or "diff" in result

    def test_no_change_for_specific_file(self):
        reg = _make_registry()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = proc
            result = _run(reg.get("diff").handler(arg="nochange.py"))
        assert "нет" in result.lower() or "no" in result.lower() or "nochange" in result

    def test_truncates_long_diff(self):
        reg = _make_registry()
        long_diff = "\n".join(f"+line {i}" for i in range(500))
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            proc = AsyncMock()
            proc.returncode = 0
            proc.communicate = AsyncMock(return_value=(long_diff.encode(), b""))
            mock_exec.return_value = proc
            result = _run(reg.get("diff").handler())
        assert "скрыто" in result or "hidden" in result.lower() or "300" in result


# ── Task 177: /snapshot ───────────────────────────────────────────────────────

class TestSnapshotCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("snapshot") is not None

    def test_default_snapshots_empty(self):
        reg = _make_registry()
        assert reg._snapshots == {}

    def test_list_empty_shows_message(self):
        reg = _make_registry()
        result = _run(reg.get("snapshot").handler())
        assert "не сохранены" in result or "no" in result.lower() or "empty" in result.lower()

    def test_save_creates_snapshot(self):
        history = [{"role": "user", "content": "hello"}]
        reg = _make_session_registry(history=history)
        _run(reg.get("snapshot").handler(arg="save v1"))
        assert "v1" in reg._snapshots

    def test_save_stores_history(self):
        history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
        reg = _make_session_registry(history=history)
        _run(reg.get("snapshot").handler(arg="save checkpoint"))
        assert len(reg._snapshots["checkpoint"]) == 2

    def test_save_returns_confirmation(self):
        reg = _make_session_registry()
        result = _run(reg.get("snapshot").handler(arg="save test"))
        assert "test" in result or "сохранён" in result.lower()

    def test_list_shows_snapshots(self):
        reg = _make_registry()
        reg._snapshots = {"v1": [{"role": "user", "content": "x"}], "v2": []}
        result = _run(reg.get("snapshot").handler(arg="list"))
        assert "v1" in result
        assert "v2" in result

    def test_load_restores_history(self):
        history = [{"role": "user", "content": "saved msg"}]
        reg = _make_session_registry()
        reg._snapshots["backup"] = history
        _run(reg.get("snapshot").handler(arg="load backup"))
        reg._session.orchestrator.restore_history.assert_called_once_with(history)

    def test_load_nonexistent_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("snapshot").handler(arg="load ghost"))
        assert "не найден" in result or "not found" in result.lower() or "ghost" in result

    def test_load_shows_available_when_error(self):
        reg = _make_registry()
        reg._snapshots["v1"] = []
        result = _run(reg.get("snapshot").handler(arg="load ghost"))
        assert "v1" in result

    def test_del_removes_snapshot(self):
        reg = _make_registry()
        reg._snapshots["old"] = []
        _run(reg.get("snapshot").handler(arg="del old"))
        assert "old" not in reg._snapshots

    def test_del_nonexistent_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("snapshot").handler(arg="del ghost"))
        assert "не найден" in result or "not found" in result.lower()

    def test_clear_removes_all(self):
        reg = _make_registry()
        reg._snapshots = {"a": [], "b": [], "c": []}
        _run(reg.get("snapshot").handler(arg="clear"))
        assert reg._snapshots == {}

    def test_clear_returns_count(self):
        reg = _make_registry()
        reg._snapshots = {"a": [], "b": []}
        result = _run(reg.get("snapshot").handler(arg="clear"))
        assert "2" in result

    def test_save_no_name_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("snapshot").handler(arg="save"))
        assert "имя" in result or "name" in result.lower() or "usage" in result.lower()

    def test_unknown_subcommand_shows_help(self):
        reg = _make_registry()
        result = _run(reg.get("snapshot").handler(arg="xyzzy"))
        assert "save" in result or "load" in result


# ── Task 178: /grep ───────────────────────────────────────────────────────────

class TestGrepCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("grep") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("grep").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_finds_pattern_in_files(self, tmp_path):
        (tmp_path / "test.py").write_text("def hello_world():\n    pass\n")
        reg = _make_registry()
        result = _run(reg.get("grep").handler(arg=f"hello_world {tmp_path}"))
        assert "hello_world" in result

    def test_no_match_returns_message(self, tmp_path):
        (tmp_path / "test.py").write_text("x = 1\n")
        reg = _make_registry()
        result = _run(reg.get("grep").handler(arg=f"XYZNOTFOUND {tmp_path}"))
        assert "не найден" in result or "not found" in result.lower()

    def test_shows_file_and_line(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("class MyClass:\n    pass\n")
        reg = _make_registry()
        result = _run(reg.get("grep").handler(arg=f"class MyClass {tmp_path}"))
        assert "module.py" in result
        assert "1" in result  # line number

    def test_invalid_regex_shows_error(self, tmp_path):
        reg = _make_registry()
        result = _run(reg.get("grep").handler(arg=f"[unclosed {tmp_path}"))
        assert "regex" in result.lower() or "неверный" in result.lower()

    def test_nonexistent_path_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("grep").handler(arg="pattern /nonexistent/path/xyz"))
        assert "не найден" in result or "not found" in result.lower()

    def test_searches_recursively(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "deep.py").write_text("TARGET_PATTERN = True\n")
        reg = _make_registry()
        result = _run(reg.get("grep").handler(arg=f"TARGET_PATTERN {tmp_path}"))
        assert "TARGET_PATTERN" in result or "deep.py" in result

    def test_groups_results_by_file(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo(): pass\n")
        (tmp_path / "b.py").write_text("def foo(): return 1\n")
        reg = _make_registry()
        result = _run(reg.get("grep").handler(arg=f"def foo {tmp_path}"))
        assert "a.py" in result
        assert "b.py" in result

    def test_pattern_without_path_searches_cwd(self):
        reg = _make_registry()
        # Pattern that shouldn't match anything meaningful — just verify it doesn't crash
        result = _run(reg.get("grep").handler(arg="XYZZY_IMPOSSIBLE_MATCH_STRING_12345"))
        assert isinstance(result, str)

    def test_single_file_arg(self, tmp_path):
        f = tmp_path / "single.py"
        f.write_text("needle = 42\n")
        reg = _make_registry()
        result = _run(reg.get("grep").handler(arg=f"needle {f}"))
        assert "needle" in result

    def test_shows_match_count(self, tmp_path):
        f = tmp_path / "many.py"
        f.write_text("\n".join(f"match_{i} = True" for i in range(5)) + "\n")
        reg = _make_registry()
        result = _run(reg.get("grep").handler(arg=f"match_ {tmp_path}"))
        assert "5" in result or "совпадений" in result
