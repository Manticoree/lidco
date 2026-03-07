"""Tests for /coverage (#226), /complexity (#227), /docstring (#228)."""

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


# ── Task 226: /coverage ───────────────────────────────────────────────────────

class TestCoverageCommand:
    def test_registered(self):
        assert _make_registry().get("coverage") is not None

    def test_returns_string(self):
        result = _run(_make_registry().get("coverage").handler())
        assert isinstance(result, str) and len(result) > 0

    def test_reads_existing_json_report(self, tmp_path, monkeypatch):
        import json
        monkeypatch.chdir(tmp_path)
        cov_data = {
            "totals": {
                "percent_covered": 75.5,
                "covered_lines": 151,
                "missing_lines": 49,
                "num_statements": 200,
            },
            "files": {
                "src/module.py": {
                    "summary": {"percent_covered": 90.0, "missing_lines": 2},
                    "missing_lines": [10, 11],
                }
            }
        }
        (tmp_path / ".coverage.json").write_text(json.dumps(cov_data))
        result = _run(_make_registry().get("coverage").handler())
        assert "75.5" in result or "75" in result

    def test_shows_percentage(self, tmp_path, monkeypatch):
        import json
        monkeypatch.chdir(tmp_path)
        cov_data = {"totals": {"percent_covered": 82.3, "covered_lines": 82, "missing_lines": 17, "num_statements": 99}, "files": {}}
        (tmp_path / ".coverage.json").write_text(json.dumps(cov_data))
        result = _run(_make_registry().get("coverage").handler())
        assert "82" in result or "%" in result

    def test_shows_bar_chart(self, tmp_path, monkeypatch):
        import json
        monkeypatch.chdir(tmp_path)
        cov_data = {"totals": {"percent_covered": 60.0, "covered_lines": 60, "missing_lines": 40, "num_statements": 100}, "files": {}}
        (tmp_path / ".coverage.json").write_text(json.dumps(cov_data))
        result = _run(_make_registry().get("coverage").handler())
        assert "█" in result or "▓" in result or "░" in result

    def test_shows_covered_lines(self, tmp_path, monkeypatch):
        import json
        monkeypatch.chdir(tmp_path)
        cov_data = {"totals": {"percent_covered": 50.0, "covered_lines": 50, "missing_lines": 50, "num_statements": 100}, "files": {}}
        (tmp_path / ".coverage.json").write_text(json.dumps(cov_data))
        result = _run(_make_registry().get("coverage").handler())
        assert "50" in result

    def test_per_file_breakdown(self, tmp_path, monkeypatch):
        import json
        monkeypatch.chdir(tmp_path)
        cov_data = {
            "totals": {"percent_covered": 70.0, "covered_lines": 70, "missing_lines": 30, "num_statements": 100},
            "files": {
                "src/auth.py": {"summary": {"percent_covered": 45.0, "missing_lines": 11}, "missing_lines": []},
                "src/utils.py": {"summary": {"percent_covered": 95.0, "missing_lines": 1}, "missing_lines": []},
            }
        }
        (tmp_path / ".coverage.json").write_text(json.dumps(cov_data))
        result = _run(_make_registry().get("coverage").handler())
        assert "auth.py" in result or "utils.py" in result

    def test_no_report_runs_pytest(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # No .coverage.json — should attempt to run pytest (will fail gracefully)
        result = _run(_make_registry().get("coverage").handler(arg=str(tmp_path)))
        assert isinstance(result, str) and len(result) > 0

    def test_shows_file_label(self, tmp_path, monkeypatch):
        import json
        monkeypatch.chdir(tmp_path)
        cov_data = {"totals": {"percent_covered": 80.0, "covered_lines": 80, "missing_lines": 20, "num_statements": 100}, "files": {}}
        (tmp_path / ".coverage.json").write_text(json.dumps(cov_data))
        result = _run(_make_registry().get("coverage").handler())
        assert "Coverage" in result or "coverage" in result.lower()


# ── Task 227: /complexity ─────────────────────────────────────────────────────

class TestComplexityCommand:
    def test_registered(self):
        assert _make_registry().get("complexity") is not None

    def test_no_arg_shows_usage(self):
        result = _run(_make_registry().get("complexity").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_shows_error(self):
        result = _run(_make_registry().get("complexity").handler(arg="/no/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_simple_function_low_complexity(self, tmp_path):
        f = tmp_path / "simple.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        result = _run(_make_registry().get("complexity").handler(arg=str(f)))
        assert "add" in result
        assert "1" in result  # CC = 1

    def test_complex_function_high_complexity(self, tmp_path):
        f = tmp_path / "complex.py"
        f.write_text(
            "def complex_func(x, y, z):\n"
            "    if x > 0:\n"
            "        if y > 0:\n"
            "            for i in range(z):\n"
            "                if i % 2 == 0:\n"
            "                    while i > 0:\n"
            "                        i -= 1\n"
            "    elif z < 0:\n"
            "        pass\n"
            "    return x\n"
        )
        result = _run(_make_registry().get("complexity").handler(arg=str(f)))
        assert "complex_func" in result
        # CC should be > 5
        import re
        nums = [int(n) for n in re.findall(r"\b\d+\b", result) if int(n) > 0]
        assert any(n > 3 for n in nums)

    def test_shows_all_functions(self, tmp_path):
        f = tmp_path / "multi.py"
        f.write_text(
            "def alpha(): return 1\n"
            "def beta(x):\n    if x: return x\n    return 0\n"
        )
        result = _run(_make_registry().get("complexity").handler(arg=str(f)))
        assert "alpha" in result
        assert "beta" in result

    def test_top_flag_limits_results(self, tmp_path):
        f = tmp_path / "many.py"
        funcs = "\n".join(
            f"def fn{i}(x):\n    if x: return x\n    return 0\n"
            for i in range(10)
        )
        f.write_text(funcs)
        result = _run(_make_registry().get("complexity").handler(arg=f"{f} --top 3"))
        # Should show at most 3 functions
        assert result.count("fn") <= 3 or "3" in result

    def test_shows_average(self, tmp_path):
        f = tmp_path / "avg.py"
        f.write_text("def a(): return 1\ndef b(): return 2\n")
        result = _run(_make_registry().get("complexity").handler(arg=str(f)))
        assert "Средняя" in result or "avg" in result.lower() or "средн" in result.lower()

    def test_shows_line_numbers(self, tmp_path):
        f = tmp_path / "lined.py"
        f.write_text("x = 1\n\ndef target():\n    return 42\n")
        result = _run(_make_registry().get("complexity").handler(arg=str(f)))
        assert "3" in result or "L3" in result  # def target() on line 3

    def test_shows_complexity_label(self, tmp_path):
        f = tmp_path / "labeled.py"
        f.write_text("def simple(): return 1\n")
        result = _run(_make_registry().get("complexity").handler(arg=str(f)))
        assert "просто" in result or "simple" in result.lower() or "✅" in result

    def test_high_complexity_warning(self, tmp_path):
        f = tmp_path / "warn.py"
        # Build a very complex function
        ifs = "\n    ".join(f"if x == {i}: return {i}" for i in range(15))
        f.write_text(f"def very_complex(x):\n    {ifs}\n    return -1\n")
        result = _run(_make_registry().get("complexity").handler(arg=str(f)))
        assert "сложно" in result or "complex" in result.lower() or "❌" in result or "🔶" in result

    def test_empty_file_shows_message(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("x = 1\n")
        result = _run(_make_registry().get("complexity").handler(arg=str(f)))
        assert "нет" in result or "no" in result.lower() or "функций" in result.lower()

    def test_syntax_error_handled(self, tmp_path):
        f = tmp_path / "broken.py"
        f.write_text("def (bad syntax:\n")
        result = _run(_make_registry().get("complexity").handler(arg=str(f)))
        assert "синтаксическ" in result.lower() or "syntax" in result.lower()


# ── Task 228: /docstring ──────────────────────────────────────────────────────

class TestDocstringCommand:
    def test_registered(self):
        assert _make_registry().get("docstring") is not None

    def test_no_session_shows_error(self):
        result = _run(_make_registry().get("docstring").handler(arg="file.py"))
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_no_arg_shows_usage(self):
        reg = _make_session_registry()
        result = _run(reg.get("docstring").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_nonexistent_file_shows_error(self):
        reg = _make_session_registry()
        result = _run(reg.get("docstring").handler(arg="/nonexistent/file.py"))
        assert "не найден" in result or "not found" in result.lower()

    def test_non_python_rejected(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text("{}")
        reg = _make_session_registry()
        result = _run(reg.get("docstring").handler(arg=str(f)))
        assert ".py" in result or "python" in result.lower()

    def test_generates_for_undocumented_function(self, tmp_path):
        f = tmp_path / "utils.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(
            return_value=MagicMock(content='"""Add two numbers.\n\nArgs:\n    a: first\n    b: second\n"""')
        )
        result = _run(reg.get("docstring").handler(arg=str(f)))
        assert "utils.py" in result or "add" in result

    def test_skips_already_documented(self, tmp_path):
        f = tmp_path / "docs.py"
        f.write_text('def foo():\n    """Already documented."""\n    pass\n')
        reg = _make_session_registry()
        result = _run(reg.get("docstring").handler(arg=str(f)))
        # No LLM call needed — already has docstrings
        assert "docstring" in result.lower() or "✅" in result or "имеют" in result

    def test_target_specific_function(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def alpha(): pass\ndef beta(): pass\n")
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="Docstring for alpha.")
        reg._session.llm.complete = cap
        result = _run(reg.get("docstring").handler(arg=f"{f} alpha"))
        assert any("alpha" in str(m) for m in captured)

    def test_skips_private_functions(self, tmp_path):
        f = tmp_path / "priv.py"
        f.write_text("def _private(): pass\ndef public(): pass\n")
        reg = _make_session_registry()
        captured = []
        async def cap(messages, **kw):
            captured.extend(messages)
            return MagicMock(content="# docstrings")
        reg._session.llm.complete = cap
        _run(reg.get("docstring").handler(arg=str(f)))
        assert not any("_private" in str(m) for m in captured)

    def test_shows_file_name_in_header(self, tmp_path):
        f = tmp_path / "mymod.py"
        f.write_text("def foo(): pass\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(return_value=MagicMock(content="Generated."))
        result = _run(reg.get("docstring").handler(arg=str(f)))
        assert "mymod.py" in result

    def test_llm_error_handled(self, tmp_path):
        f = tmp_path / "err.py"
        f.write_text("def foo(): pass\n")
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(side_effect=Exception("LLM error"))
        result = _run(reg.get("docstring").handler(arg=str(f)))
        assert "ошибка" in result.lower() or "error" in result.lower()

    def test_missing_function_target_shows_error(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def real_func(): pass\n")
        reg = _make_session_registry()
        result = _run(reg.get("docstring").handler(arg=f"{f} nonexistent_func"))
        assert "не найдена" in result or "not found" in result.lower() or "docstring" in result.lower()
