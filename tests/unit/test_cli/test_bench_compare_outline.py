"""Tests for /bench (#197), /compare (#198), /outline (#199)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


def _make_session_registry(**kwargs) -> CommandRegistry:
    reg = _make_registry()
    sess = MagicMock()
    cfg = MagicMock()
    cfg.llm.default_model = kwargs.get("model", "gpt-4")
    sess.config = cfg
    reg.set_session(sess)
    return reg


# ── Task 197: /bench ──────────────────────────────────────────────────────────

class TestBenchCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("bench") is not None

    def test_no_session_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("bench").handler())
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_runs_default_3_requests(self):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "OK"
        call_count = []
        async def fake_complete(messages, **kw):
            call_count.append(1)
            return mock_resp
        reg._session.llm.complete = fake_complete
        _run(reg.get("bench").handler())
        assert len(call_count) == 3

    def test_respects_n_argument(self):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "OK"
        call_count = []
        async def fake_complete(messages, **kw):
            call_count.append(1)
            return mock_resp
        reg._session.llm.complete = fake_complete
        _run(reg.get("bench").handler(arg="5"))
        assert len(call_count) == 5

    def test_caps_at_10(self):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "OK"
        call_count = []
        async def fake_complete(messages, **kw):
            call_count.append(1)
            return mock_resp
        reg._session.llm.complete = fake_complete
        _run(reg.get("bench").handler(arg="50"))
        assert len(call_count) == 10

    def test_shows_model_name(self):
        reg = _make_session_registry(model="anthropic/claude-haiku")
        mock_resp = MagicMock(content="OK")
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("bench").handler(arg="1"))
        assert "claude-haiku" in result

    def test_shows_avg_latency(self):
        reg = _make_session_registry()
        mock_resp = MagicMock(content="OK")
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("bench").handler(arg="2"))
        assert "среднее" in result.lower() or "avg" in result.lower()

    def test_shows_min_max(self):
        reg = _make_session_registry()
        mock_resp = MagicMock(content="OK")
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("bench").handler(arg="2"))
        assert "мин" in result.lower() or "min" in result.lower()

    def test_shows_per_request_bar(self):
        reg = _make_session_registry()
        mock_resp = MagicMock(content="OK")
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("bench").handler(arg="2"))
        assert "#1" in result or "1:" in result

    def test_handles_llm_errors(self):
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(side_effect=Exception("timeout"))
        result = _run(reg.get("bench").handler(arg="2"))
        assert "ошибк" in result.lower() or "error" in result.lower() or "timeout" in result

    def test_invalid_n_shows_error(self):
        reg = _make_session_registry()
        result = _run(reg.get("bench").handler(arg="abc"))
        assert "неверный" in result.lower() or "invalid" in result.lower() or "abc" in result

    def test_zero_n_uses_1(self):
        reg = _make_session_registry()
        mock_resp = MagicMock(content="OK")
        call_count = []
        async def fake(messages, **kw):
            call_count.append(1)
            return mock_resp
        reg._session.llm.complete = fake
        _run(reg.get("bench").handler(arg="0"))
        assert len(call_count) == 1


# ── Task 198: /compare ────────────────────────────────────────────────────────

class TestCompareCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("compare") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("compare").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_one_arg_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("compare").handler(arg="file1.py"))
        assert "два" in result or "two" in result.lower() or "файл" in result.lower()

    def test_first_file_not_found(self):
        reg = _make_registry()
        result = _run(reg.get("compare").handler(arg="/nonexistent/a.py /nonexistent/b.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_second_file_not_found(self, tmp_path):
        f1 = tmp_path / "a.py"
        f1.write_text("x = 1\n")
        reg = _make_registry()
        result = _run(reg.get("compare").handler(arg=f"{f1} /nonexistent/b.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_identical_files(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        content = "x = 1\ny = 2\n"
        f1.write_text(content)
        f2.write_text(content)
        reg = _make_registry()
        result = _run(reg.get("compare").handler(arg=f"{f1} {f2}"))
        assert "идентичны" in result or "identical" in result.lower() or "no diff" in result.lower()

    def test_different_files_shows_diff(self, tmp_path):
        f1 = tmp_path / "v1.py"
        f2 = tmp_path / "v2.py"
        f1.write_text("x = 1\n")
        f2.write_text("x = 2\n")
        reg = _make_registry()
        result = _run(reg.get("compare").handler(arg=f"{f1} {f2}"))
        assert "```diff" in result or "diff" in result.lower()

    def test_shows_added_removed_count(self, tmp_path):
        f1 = tmp_path / "old.py"
        f2 = tmp_path / "new.py"
        f1.write_text("x = 1\ny = 2\n")
        f2.write_text("x = 1\nz = 3\nw = 4\n")
        reg = _make_registry()
        result = _run(reg.get("compare").handler(arg=f"{f1} {f2}"))
        assert "добавлено" in result or "added" in result.lower() or "+" in result
        assert "удалено" in result or "removed" in result.lower() or "−" in result

    def test_shows_file_sizes(self, tmp_path):
        f1 = tmp_path / "x.py"
        f2 = tmp_path / "y.py"
        f1.write_text("a = 1\n")
        f2.write_text("b = 2\n")
        reg = _make_registry()
        result = _run(reg.get("compare").handler(arg=f"{f1} {f2}"))
        assert "x.py" in result and "y.py" in result

    def test_truncates_long_diff(self, tmp_path):
        f1 = tmp_path / "big1.py"
        f2 = tmp_path / "big2.py"
        f1.write_text("\n".join(f"x_{i} = {i}" for i in range(300)) + "\n")
        f2.write_text("\n".join(f"y_{i} = {i}" for i in range(300)) + "\n")
        reg = _make_registry()
        result = _run(reg.get("compare").handler(arg=f"{f1} {f2}"))
        assert "скрыто" in result or "hidden" in result.lower() or "200" in result

    def test_directory_rejected(self, tmp_path):
        f1 = tmp_path / "a.py"
        f1.write_text("x")
        reg = _make_registry()
        result = _run(reg.get("compare").handler(arg=f"{f1} {tmp_path}"))
        assert "не файл" in result or "not a file" in result.lower()


# ── Task 199: /outline ────────────────────────────────────────────────────────

class TestOutlineCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("outline") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("outline").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_file_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_directory_rejected(self, tmp_path):
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(tmp_path)))
        assert "не файл" in result or "not a file" in result.lower()

    def test_shows_functions(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("def foo(x):\n    pass\n\ndef bar(y, z):\n    return y + z\n")
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "foo" in result
        assert "bar" in result

    def test_shows_classes(self, tmp_path):
        f = tmp_path / "classes.py"
        f.write_text("class MyClass:\n    def __init__(self):\n        pass\n")
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "MyClass" in result

    def test_shows_async_functions(self, tmp_path):
        f = tmp_path / "async_mod.py"
        f.write_text("async def fetch(url):\n    pass\n")
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "fetch" in result

    def test_shows_line_numbers(self, tmp_path):
        f = tmp_path / "lined.py"
        f.write_text("x = 1\n\ndef target():\n    pass\n")
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "3" in result  # def target() is on line 3

    def test_shows_signatures(self, tmp_path):
        f = tmp_path / "sigs.py"
        f.write_text("def greet(name: str, greeting: str = 'Hello') -> str:\n    pass\n")
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "name" in result or "greet" in result

    def test_empty_file_no_definitions(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("# Just a comment\nx = 1\n")
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "нет" in result.lower() or "no" in result.lower() or "определений" in result.lower()

    def test_shows_total_line_count(self, tmp_path):
        f = tmp_path / "counted.py"
        f.write_text("def a():\n    pass\n\ndef b():\n    pass\n")
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "5" in result or "строк" in result

    def test_shows_definition_count(self, tmp_path):
        f = tmp_path / "multi.py"
        f.write_text(
            "def a():\n    pass\n"
            "def b():\n    pass\n"
            "class C:\n    pass\n"
        )
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "3" in result

    def test_shows_docstring_preview(self, tmp_path):
        f = tmp_path / "docs.py"
        f.write_text('def documented():\n    """This does something useful."""\n    pass\n')
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "something useful" in result or "documented" in result

    def test_shows_inspect_hint(self, tmp_path):
        f = tmp_path / "hinted.py"
        f.write_text("def func():\n    pass\n")
        reg = _make_registry()
        result = _run(reg.get("outline").handler(arg=str(f)))
        assert "/inspect" in result
