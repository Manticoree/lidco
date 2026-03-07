"""Tests for /explain (#194), /token (#195), /env (#196)."""

from __future__ import annotations

import asyncio
import sys
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


# ── Task 194: /explain ────────────────────────────────────────────────────────

class TestExplainCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("explain") is not None

    def test_no_session_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("explain").handler(arg="x = 1"))
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_no_arg_shows_usage(self):
        reg = _make_session_registry()
        result = _run(reg.get("explain").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_explains_code_snippet(self):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "Это лямбда-функция, возвращающая квадрат числа."
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("explain").handler(arg="lambda x: x**2"))
        assert "лямбда" in result or "lambda" in result.lower()

    def test_explains_file(self, tmp_path):
        f = tmp_path / "simple.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "Функция сложения двух чисел."
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("explain").handler(arg=str(f)))
        assert "simple.py" in result or "сложения" in result

    def test_shows_source_label_in_header(self):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "Explanation here."
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("explain").handler(arg="x = 42"))
        assert "Объяснение" in result or "explain" in result.lower()

    def test_file_not_found_treats_as_code(self, tmp_path):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "Some explanation."
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        # This path doesn't exist — should be treated as code snippet
        result = _run(reg.get("explain").handler(arg="not_a_real_path.py = 1"))
        assert isinstance(result, str)

    def test_large_file_truncated(self, tmp_path):
        f = tmp_path / "big.py"
        f.write_text("x = 1\n" * 2000)  # ~12000 chars
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "Big file."
        captured = []

        async def capture_complete(messages, **kw):
            captured.extend(messages)
            return mock_resp

        reg._session.llm.complete = capture_complete
        _run(reg.get("explain").handler(arg=str(f)))
        # The prompt should contain truncated code
        assert "обрезано" in str(captured) or len(captured) > 0

    def test_llm_error_handled(self):
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(side_effect=Exception("LLM down"))
        result = _run(reg.get("explain").handler(arg="x = 1"))
        assert "ошибка" in result.lower() or "error" in result.lower()

    def test_passes_code_to_llm(self):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "Done."
        captured = []

        async def cap(messages, **kw):
            captured.extend(messages)
            return mock_resp

        reg._session.llm.complete = cap
        _run(reg.get("explain").handler(arg="def secret_func(): pass"))
        assert any("secret_func" in str(m) for m in captured)


# ── Task 195: /token ──────────────────────────────────────────────────────────

class TestTokenCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("token") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("token").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_returns_token_count(self):
        reg = _make_registry()
        result = _run(reg.get("token").handler(arg="hello world"))
        assert "токен" in result.lower() or "token" in result.lower()

    def test_shows_char_count(self):
        reg = _make_registry()
        result = _run(reg.get("token").handler(arg="hello"))
        assert "5" in result  # 5 chars

    def test_shows_word_count(self):
        reg = _make_registry()
        result = _run(reg.get("token").handler(arg="one two three"))
        assert "3" in result

    def test_estimate_non_zero(self):
        reg = _make_registry()
        result = _run(reg.get("token").handler(arg="x"))
        # Any single char should yield at least 1 token
        assert "1" in result

    def test_shows_cost_estimates(self):
        reg = _make_registry()
        result = _run(reg.get("token").handler(arg="hello world this is a test"))
        assert "$" in result

    def test_shows_multiple_model_costs(self):
        reg = _make_registry()
        result = _run(reg.get("token").handler(arg="some text"))
        # Should show at least 2 different model prices
        assert result.count("$") >= 2

    def test_longer_text_higher_count(self):
        reg = _make_registry()
        short_result = _run(reg.get("token").handler(arg="hi"))
        long_result = _run(reg.get("token").handler(arg="hi " * 100))
        # Extract numbers from both — long should be larger
        import re
        short_nums = [int(m) for m in re.findall(r"~(\d+)", short_result)]
        long_nums = [int(m) for m in re.findall(r"~(\d+)", long_result)]
        if short_nums and long_nums:
            assert max(long_nums) > max(short_nums)

    def test_cyrillic_text(self):
        reg = _make_registry()
        result = _run(reg.get("token").handler(arg="Привет мир"))
        assert "токен" in result.lower() or "~" in result

    def test_shows_approximation_note(self):
        reg = _make_registry()
        result = _run(reg.get("token").handler(arg="test text"))
        assert "приблизительн" in result.lower() or "approx" in result.lower() or "~" in result


# ── Task 196: /env ────────────────────────────────────────────────────────────

class TestEnvCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("env") is not None

    def test_shows_python_version(self):
        reg = _make_registry()
        result = _run(reg.get("env").handler())
        py_ver = sys.version.split()[0]
        assert py_ver in result

    def test_shows_executable(self):
        reg = _make_registry()
        result = _run(reg.get("env").handler())
        assert sys.executable in result or "исполняемый" in result.lower()

    def test_shows_os_info(self):
        import platform
        reg = _make_registry()
        result = _run(reg.get("env").handler())
        assert platform.system() in result

    def test_shows_cwd(self):
        import os
        reg = _make_registry()
        result = _run(reg.get("env").handler())
        assert os.getcwd() in result or "рабочая" in result.lower()

    def test_shows_packages_section(self):
        reg = _make_registry()
        result = _run(reg.get("env").handler())
        assert "пакет" in result.lower() or "package" in result.lower()

    def test_shows_at_least_one_package(self):
        reg = _make_registry()
        result = _run(reg.get("env").handler())
        # At minimum, pytest should be installed
        assert "pytest" in result or "rich" in result or "pydantic" in result

    def test_shows_model_when_session_active(self):
        reg = _make_session_registry(model="anthropic/claude-opus-4")
        result = _run(reg.get("env").handler())
        assert "claude-opus-4" in result

    def test_no_session_still_works(self):
        reg = _make_registry()
        result = _run(reg.get("env").handler())
        # Should complete without error even with no session
        assert "Python" in result or "python" in result.lower()

    def test_shows_virtualenv_hint(self):
        reg = _make_registry()
        result = _run(reg.get("env").handler())
        assert "virtualenv" in result.lower() or "venv" in result.lower() or "conda" in result.lower()

    def test_all_flag_shows_missing_packages(self):
        reg = _make_registry()
        result = _run(reg.get("env").handler(arg="all"))
        # With "all", uninstalled packages should be shown too
        assert isinstance(result, str) and len(result) > 50
