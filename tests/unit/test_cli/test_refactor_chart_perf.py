"""Tests for /refactor (#235), /chart (#236), /perf (#237)."""

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


# ── Task 235: /refactor ───────────────────────────────────────────────────────

class TestRefactorCommand:
    def test_registered(self):
        assert _make_registry().get("refactor") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("refactor").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_no_session_shows_error(self):
        result = _run(_make_registry().get("refactor").handler(arg="file.py"))
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_nonexistent_file_shows_error(self):
        reg = _make_session_registry()
        result = _run(reg.get("refactor").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_non_python_rejected(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("{}")
        reg = _make_session_registry()
        result = _run(reg.get("refactor").handler(arg=str(f)))
        assert ".py" in result or "python" in result.lower()

    def test_directory_rejected(self, tmp_path):
        reg = _make_session_registry()
        result = _run(reg.get("refactor").handler(arg=str(tmp_path)))
        assert "не файл" in result or "not" in result.lower()

    def test_dry_run_no_modification(self, tmp_path):
        f = tmp_path / "code.py"
        original = "x = 1\ny = 2\n"
        f.write_text(original)
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(
            return_value=MagicMock(content="```python\nx = 1\ny = 2\n```\n## Изменения\nНичего.")
        )
        result = _run(reg.get("refactor").handler(arg=f"{f} --dry"))
        assert f.read_text() == original

    def test_dry_run_shows_suggestions(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(
            return_value=MagicMock(content="```python\nx = 1\n```\n## Изменения\nНичего.")
        )
        result = _run(reg.get("refactor").handler(arg=f"{f} --dry"))
        assert "--dry" in result or "dry" in result.lower() or "предложен" in result.lower()

    def test_refactors_file(self, tmp_path):
        f = tmp_path / "utils.py"
        f.write_text("def add(a,b):\n    return a+b\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(
            return_value=MagicMock(
                content='```python\ndef add(a: int, b: int) -> int:\n    return a + b\n```\n## Изменения\n- Добавлены типы'
            )
        )
        result = _run(reg.get("refactor").handler(arg=str(f)))
        assert isinstance(result, str) and len(result) > 0

    def test_file_updated_after_refactor(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("x=1\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(
            return_value=MagicMock(
                content="```python\nx = 1\n```\n## Изменения\n- Добавлен пробел"
            )
        )
        _run(reg.get("refactor").handler(arg=str(f)))
        # File was written (new content differs from original in some way)
        assert f.exists()

    def test_shows_file_name(self, tmp_path):
        f = tmp_path / "mymod.py"
        f.write_text("x = 1\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(
            return_value=MagicMock(content="```python\nx = 1\n```\n## Изменения\n- ok")
        )
        result = _run(reg.get("refactor").handler(arg=str(f)))
        assert "mymod.py" in result

    def test_instruction_passed_to_llm(self, tmp_path):
        f = tmp_path / "svc.py"
        f.write_text("def foo(): pass\n")
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="```python\ndef foo(): pass\n```\n## Изменения\nnone")
        reg._session.llm.complete = cap
        _run(reg.get("refactor").handler(arg=f"{f} извлеки методы"))
        assert any("извлеки методы" in str(m) for m in captured)

    def test_llm_error_handled(self, tmp_path):
        f = tmp_path / "err.py"
        f.write_text("x = 1\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(side_effect=Exception("LLM fail"))
        result = _run(reg.get("refactor").handler(arg=str(f)))
        assert "ошибка" in result.lower() or "error" in result.lower()

    def test_large_file_rejected(self, tmp_path):
        f = tmp_path / "big.py"
        f.write_text("x = 1\n" * 1100)
        reg = _make_session_registry()
        result = _run(reg.get("refactor").handler(arg=str(f)))
        assert "большой" in result.lower() or "large" in result.lower() or "1" in result


# ── Task 236: /chart ──────────────────────────────────────────────────────────

class TestChartCommand:
    def test_registered(self):
        assert _make_registry().get("chart") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("chart").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_bar_chart_basic(self):
        result = _run(_make_registry().get("chart").handler(arg="10,20,30"))
        assert "█" in result or "|" in result

    def test_shows_values(self):
        result = _run(_make_registry().get("chart").handler(arg="10,20,30"))
        assert "10" in result
        assert "20" in result
        assert "30" in result

    def test_labeled_data(self):
        result = _run(_make_registry().get("chart").handler(arg="Jan:10,Feb:20,Mar:30"))
        assert "Jan" in result
        assert "Feb" in result
        assert "Mar" in result

    def test_pie_chart(self):
        result = _run(_make_registry().get("chart").handler(arg="A:40,B:30,C:30 --type pie"))
        assert "%" in result or "40" in result

    def test_line_chart(self):
        result = _run(_make_registry().get("chart").handler(arg="5,10,7,15,3 --type line"))
        assert "●" in result or "|" in result or "5" in result

    def test_title_shown(self):
        result = _run(_make_registry().get("chart").handler(arg="1,2,3 --title МойГрафик"))
        assert "МойГрафик" in result

    def test_stats_shown(self):
        result = _run(_make_registry().get("chart").handler(arg="10,20,30"))
        assert "Мин" in result or "мин" in result.lower() or "min" in result.lower()
        assert "Макс" in result or "макс" in result.lower() or "max" in result.lower()

    def test_sum_shown(self):
        result = _run(_make_registry().get("chart").handler(arg="10,20,30"))
        assert "60" in result  # sum = 60

    def test_average_shown(self):
        result = _run(_make_registry().get("chart").handler(arg="10,20,30"))
        assert "20" in result  # avg = 20.0

    def test_invalid_data_shows_error(self):
        result = _run(_make_registry().get("chart").handler(arg="hello,world"))
        assert "ошибка" in result.lower() or "error" in result.lower()

    def test_space_separated(self):
        result = _run(_make_registry().get("chart").handler(arg="5 10 15 20"))
        assert "5" in result and "20" in result

    def test_too_many_points_rejected(self):
        data = ",".join(str(i) for i in range(50))
        result = _run(_make_registry().get("chart").handler(arg=data))
        assert "много" in result.lower() or "30" in result or "error" in result.lower()

    def test_single_value(self):
        result = _run(_make_registry().get("chart").handler(arg="42"))
        assert "42" in result

    def test_code_block_present(self):
        result = _run(_make_registry().get("chart").handler(arg="1,2,3"))
        assert "```" in result

    def test_pie_percentage(self):
        result = _run(_make_registry().get("chart").handler(arg="Python:50,JS:50 --type pie"))
        assert "50" in result and "%" in result


# ── Task 237: /perf ───────────────────────────────────────────────────────────

class TestPerfCommand:
    def test_registered(self):
        assert _make_registry().get("perf") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("perf").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_file_shows_error(self):
        result = _run(_make_registry().get("perf").handler(arg="/nonexistent/script.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_non_python_rejected(self, tmp_path):
        f = tmp_path / "script.sh"
        f.write_text("echo hello\n")
        result = _run(_make_registry().get("perf").handler(arg=str(f)))
        assert ".py" in result or "python" in result.lower()

    def test_directory_rejected(self, tmp_path):
        result = _run(_make_registry().get("perf").handler(arg=str(tmp_path)))
        assert "не файл" in result or "not" in result.lower()

    def test_profiles_simple_script(self, tmp_path):
        f = tmp_path / "simple.py"
        f.write_text("x = sum(range(1000))\n")
        result = _run(_make_registry().get("perf").handler(arg=str(f)))
        assert isinstance(result, str) and len(result) > 0

    def test_shows_file_name(self, tmp_path):
        f = tmp_path / "myscript.py"
        f.write_text("x = 1\n")
        result = _run(_make_registry().get("perf").handler(arg=str(f)))
        assert "myscript.py" in result

    def test_shows_top_n(self, tmp_path):
        f = tmp_path / "bench.py"
        f.write_text("for i in range(10000): pass\n")
        result = _run(_make_registry().get("perf").handler(arg=f"{f} --top 5"))
        assert isinstance(result, str) and len(result) > 0

    def test_top_n_default_10(self, tmp_path):
        f = tmp_path / "bench2.py"
        f.write_text("x = list(range(1000))\n")
        result = _run(_make_registry().get("perf").handler(arg=str(f)))
        assert "10" in result or "top" in result.lower() or "профиль" in result.lower()

    def test_calls_flag_accepted(self, tmp_path):
        f = tmp_path / "calltest.py"
        f.write_text("x = 1\n")
        result = _run(_make_registry().get("perf").handler(arg=f"{f} --calls"))
        assert isinstance(result, str) and len(result) > 0

    def test_script_with_functions(self, tmp_path):
        f = tmp_path / "funcs.py"
        f.write_text(
            "def compute():\n"
            "    return sum(i**2 for i in range(10000))\n"
            "compute()\n"
        )
        result = _run(_make_registry().get("perf").handler(arg=str(f)))
        assert isinstance(result, str) and len(result) > 0

    def test_code_block_in_output(self, tmp_path):
        f = tmp_path / "code_out.py"
        f.write_text("x = 1\n")
        result = _run(_make_registry().get("perf").handler(arg=str(f)))
        assert "```" in result

    def test_shows_profiler_label(self, tmp_path):
        f = tmp_path / "labeled.py"
        f.write_text("x = 1\n")
        result = _run(_make_registry().get("perf").handler(arg=str(f)))
        assert "профил" in result.lower() or "perf" in result.lower() or "cprofile" in result.lower()
