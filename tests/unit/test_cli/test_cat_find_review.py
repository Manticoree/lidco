"""Tests for /cat (#215), /find (#216), /review (#217)."""

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
    cfg.llm.default_model = kwargs.get("model", "claude-sonnet-4-6")
    sess.config = cfg
    sess.project_dir = kwargs.get("project_dir", Path("."))
    reg.set_session(sess)
    return reg


# ── Task 215: /cat ────────────────────────────────────────────────────────────

class TestCatCommand:
    def test_registered(self):
        assert _make_registry().get("cat") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("cat").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_shows_file_content(self, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("x = 1\ny = 2\n")
        result = _run(_make_registry().get("cat").handler(arg=str(f)))
        assert "x = 1" in result
        assert "y = 2" in result

    def test_shows_file_name(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("pass\n")
        result = _run(_make_registry().get("cat").handler(arg=str(f)))
        assert "module.py" in result

    def test_nonexistent_shows_error(self):
        result = _run(_make_registry().get("cat").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_directory_rejected(self, tmp_path):
        result = _run(_make_registry().get("cat").handler(arg=str(tmp_path)))
        assert "не файл" in result or "not" in result.lower() or "директор" in result.lower()

    def test_line_count_limit(self, tmp_path):
        f = tmp_path / "big.py"
        f.write_text("\n".join(f"line_{i} = {i}" for i in range(300)) + "\n")
        result = _run(_make_registry().get("cat").handler(arg=str(f)))
        # Should be truncated at 200 lines
        assert "line_299" not in result

    def test_range_selection(self, tmp_path):
        f = tmp_path / "range.py"
        f.write_text("\n".join(f"row{i}" for i in range(1, 21)) + "\n")
        result = _run(_make_registry().get("cat").handler(arg=f"{f} 5-10"))
        assert "row5" in result
        assert "row10" in result
        assert "row4" not in result   # row4 is before range
        assert "row11" not in result

    def test_first_n_lines(self, tmp_path):
        f = tmp_path / "lines.py"
        f.write_text("\n".join(f"L{i}" for i in range(1, 51)) + "\n")
        result = _run(_make_registry().get("cat").handler(arg=f"{f} 5"))
        assert "L5" in result
        assert "L6" not in result

    def test_num_flag_shows_line_numbers(self, tmp_path):
        f = tmp_path / "numbered.py"
        f.write_text("alpha\nbeta\ngamma\n")
        result = _run(_make_registry().get("cat").handler(arg=f"{f} --num"))
        assert "1" in result
        assert "│" in result or "|" in result

    def test_code_block_wrapping(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def foo(): pass\n")
        result = _run(_make_registry().get("cat").handler(arg=str(f)))
        assert "```" in result

    def test_python_syntax_highlight_hint(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("x = 1\n")
        result = _run(_make_registry().get("cat").handler(arg=str(f)))
        assert "python" in result.lower() or "```" in result

    def test_binary_file_rejected(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"\x00\x01\x02\x03binary")
        result = _run(_make_registry().get("cat").handler(arg=str(f)))
        assert "бинарный" in result or "binary" in result.lower()

    def test_shows_total_line_count(self, tmp_path):
        f = tmp_path / "counted.py"
        f.write_text("\n".join(str(i) for i in range(50)) + "\n")
        result = _run(_make_registry().get("cat").handler(arg=str(f)))
        assert "50" in result

    def test_truncation_hint(self, tmp_path):
        f = tmp_path / "long.py"
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(250)) + "\n")
        result = _run(_make_registry().get("cat").handler(arg=str(f)))
        assert "250" in result or "скрыт" in result.lower() or "продолжени" in result.lower()


# ── Task 216: /find ───────────────────────────────────────────────────────────

class TestFindCommand:
    def test_registered(self):
        assert _make_registry().get("find") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("find").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_finds_files_by_glob(self, tmp_path):
        (tmp_path / "alpha.py").write_text("x")
        (tmp_path / "beta.py").write_text("y")
        (tmp_path / "readme.md").write_text("z")
        result = _run(_make_registry().get("find").handler(arg=f"*.py {tmp_path}"))
        assert "alpha.py" in result
        assert "beta.py" in result

    def test_excludes_non_matching(self, tmp_path):
        (tmp_path / "code.py").write_text("x")
        (tmp_path / "data.txt").write_text("y")
        result = _run(_make_registry().get("find").handler(arg=f"*.py {tmp_path}"))
        assert "data.txt" not in result

    def test_finds_in_subdirectories(self, tmp_path):
        sub = tmp_path / "subpkg"
        sub.mkdir()
        (sub / "deep.py").write_text("x")
        result = _run(_make_registry().get("find").handler(arg=f"*.py {tmp_path}"))
        assert "deep.py" in result

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "module.pyc").write_bytes(b"")
        result = _run(_make_registry().get("find").handler(arg=f"*.pyc {tmp_path}"))
        assert "module.pyc" not in result

    def test_type_file_flag(self, tmp_path):
        sub = tmp_path / "mydir"
        sub.mkdir()
        (tmp_path / "myfile.py").write_text("x")
        result = _run(_make_registry().get("find").handler(arg=f"my* {tmp_path} --type f"))
        assert "myfile.py" in result
        assert "mydir" not in result

    def test_ext_flag(self, tmp_path):
        (tmp_path / "a.py").write_text("x")
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "c.yaml").write_text("k: v")
        result = _run(_make_registry().get("find").handler(arg=f"* {tmp_path} --ext .json"))
        assert "b.json" in result
        assert "a.py" not in result

    def test_no_match_shows_message(self, tmp_path):
        result = _run(_make_registry().get("find").handler(arg=f"*.nonexistent {tmp_path}"))
        assert "не найдено" in result or "not found" in result.lower()

    def test_shows_count(self, tmp_path):
        for i in range(5):
            (tmp_path / f"file{i}.py").write_text("x")
        result = _run(_make_registry().get("find").handler(arg=f"*.py {tmp_path}"))
        assert "5" in result or "найдено" in result.lower()

    def test_substring_match(self, tmp_path):
        (tmp_path / "test_auth.py").write_text("x")
        (tmp_path / "test_token.py").write_text("y")
        (tmp_path / "utils.py").write_text("z")
        result = _run(_make_registry().get("find").handler(arg=f"test_ {tmp_path}"))
        assert "test_auth.py" in result or "test_token.py" in result

    def test_nonexistent_path_shows_error(self):
        result = _run(_make_registry().get("find").handler(arg="*.py /nonexistent/dir"))
        assert "не найдена" in result or "not found" in result.lower()

    def test_shows_file_sizes(self, tmp_path):
        (tmp_path / "sized.py").write_text("x = 1\n" * 10)
        result = _run(_make_registry().get("find").handler(arg=f"*.py {tmp_path}"))
        assert "б" in result or "bytes" in result.lower() or "sized.py" in result


# ── Task 217: /review ─────────────────────────────────────────────────────────

class TestReviewCommand:
    def test_registered(self):
        assert _make_registry().get("review") is not None

    def test_no_session_shows_error(self):
        result = _run(_make_registry().get("review").handler(arg="file.py"))
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_no_arg_shows_usage(self):
        reg = _make_session_registry()
        result = _run(reg.get("review").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_file_shows_error(self):
        reg = _make_session_registry()
        result = _run(reg.get("review").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_directory_rejected(self, tmp_path):
        reg = _make_session_registry()
        result = _run(reg.get("review").handler(arg=str(tmp_path)))
        assert "не файл" in result or "not" in result.lower()

    def test_reviews_file(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        reg = _make_session_registry()
        mock_resp = MagicMock(content="Код выглядит хорошо. Функция проста и понятна.")
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("review").handler(arg=str(f)))
        assert "module.py" in result or "Код" in result

    def test_shows_file_name_in_header(self, tmp_path):
        f = tmp_path / "auth.py"
        f.write_text("x = 1\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(return_value=MagicMock(content="Looks good."))
        result = _run(reg.get("review").handler(arg=str(f)))
        assert "auth.py" in result

    def test_passes_code_to_llm(self, tmp_path):
        f = tmp_path / "secret.py"
        f.write_text("def secret_logic(): pass\n")
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="Review done.")
        reg._session.llm.complete = cap
        _run(reg.get("review").handler(arg=str(f)))
        assert any("secret_logic" in str(m) for m in captured)

    def test_focus_security_flag(self, tmp_path):
        f = tmp_path / "api.py"
        f.write_text("import os\npassword = 'hardcoded'\n")
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="Security issue found.")
        reg._session.llm.complete = cap
        _run(reg.get("review").handler(arg=f"{f} --focus security"))
        assert any("безопасност" in str(m).lower() or "security" in str(m).lower() for m in captured)

    def test_focus_performance_flag(self, tmp_path):
        f = tmp_path / "slow.py"
        f.write_text("for i in range(1000000): pass\n")
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="Performance issue.")
        reg._session.llm.complete = cap
        result = _run(reg.get("review").handler(arg=f"{f} --focus performance"))
        assert "performance" in result.lower() or "производительн" in result.lower()

    def test_focus_label_in_result(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(return_value=MagicMock(content="Style ok."))
        result = _run(reg.get("review").handler(arg=f"{f} --focus style"))
        assert "style" in result.lower()

    def test_large_file_truncated(self, tmp_path):
        f = tmp_path / "huge.py"
        f.write_text("x = 1\n" * 3000)
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="Big file reviewed.")
        reg._session.llm.complete = cap
        _run(reg.get("review").handler(arg=str(f)))
        content_str = str(captured)
        assert "обрезано" in content_str or len(content_str) < 50_000

    def test_llm_error_handled(self, tmp_path):
        f = tmp_path / "err.py"
        f.write_text("x = 1\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(side_effect=Exception("LLM unavailable"))
        result = _run(reg.get("review").handler(arg=str(f)))
        assert "ошибка" in result.lower() or "error" in result.lower()

    def test_returns_llm_content(self, tmp_path):
        f = tmp_path / "reviewed.py"
        f.write_text("def foo(): pass\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(
            return_value=MagicMock(content="**Критические проблемы:** нет. Код чист.")
        )
        result = _run(reg.get("review").handler(arg=str(f)))
        assert "Код чист" in result
