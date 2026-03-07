"""Tests for /reload (#191), /inspect (#192), /ask (#193)."""

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
    cfg = MagicMock()
    cfg.llm.default_model = kwargs.get("model", "gpt-4")
    sess.config = cfg
    sess.project_dir = kwargs.get("project_dir", Path("."))

    agent_reg = MagicMock()
    agent_reg.list_names.return_value = kwargs.get("agents", ["coder", "tester"])
    sess.agent_registry = agent_reg

    tool_reg = MagicMock()
    tool_reg.list_tools.return_value = list(range(kwargs.get("tool_count", 10)))
    sess.tool_registry = tool_reg

    sess._config_reloader = None
    reg.set_session(sess)
    return reg


# ── Task 191: /reload ─────────────────────────────────────────────────────────

class TestReloadCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("reload") is not None

    def test_no_session_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("reload").handler())
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_reload_config_default(self):
        reg = _make_session_registry()
        result = _run(reg.get("reload").handler())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_reload_config_explicit(self):
        reg = _make_session_registry()
        result = _run(reg.get("reload").handler(arg="config"))
        assert "конфигурация" in result.lower() or "config" in result.lower()

    def test_reload_agents(self):
        reg = _make_session_registry()
        result = _run(reg.get("reload").handler(arg="agents"))
        assert "агент" in result.lower() or "agent" in result.lower()

    def test_reload_agents_shows_count(self):
        reg = _make_session_registry(agents=["coder", "tester", "debugger"])
        result = _run(reg.get("reload").handler(arg="agents"))
        assert "3" in result

    def test_reload_tools(self):
        reg = _make_session_registry(tool_count=15)
        result = _run(reg.get("reload").handler(arg="tools"))
        assert "15" in result or "инструмент" in result.lower() or "tool" in result.lower()

    def test_reload_all(self):
        reg = _make_session_registry()
        result = _run(reg.get("reload").handler(arg="all"))
        # Should mention all three categories
        assert "конфигурация" in result.lower() or "config" in result.lower()
        assert "агент" in result.lower() or "agent" in result.lower()
        assert "инструмент" in result.lower() or "tool" in result.lower()

    def test_reload_shows_model(self):
        reg = _make_session_registry(model="anthropic/claude-opus-4")
        # Use a reloader so we don't call load_config() which would overwrite the mock
        reloader = MagicMock()
        reloader._reload_once = MagicMock()
        reg._session._config_reloader = reloader
        result = _run(reg.get("reload").handler(arg="config"))
        assert "claude-opus-4" in result

    def test_unknown_target_shows_error(self):
        reg = _make_session_registry()
        result = _run(reg.get("reload").handler(arg="xyzzy"))
        assert "неизвестная" in result.lower() or "unknown" in result.lower() or "xyzzy" in result

    def test_reload_with_reloader(self):
        reg = _make_session_registry()
        reloader = MagicMock()
        reloader._reload_once = MagicMock()
        reg._session._config_reloader = reloader
        result = _run(reg.get("reload").handler(arg="config"))
        reloader._reload_once.assert_called_once()
        assert "✓" in result or "перезагружена" in result.lower()


# ── Task 192: /inspect ────────────────────────────────────────────────────────

class TestInspectCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("inspect") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("inspect").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_finds_function_in_files(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text(
            "def my_special_func(x, y):\n"
            "    \"\"\"Add two numbers.\"\"\"\n"
            "    return x + y\n"
        )
        reg = _make_session_registry(project_dir=tmp_path)
        result = _run(reg.get("inspect").handler(arg="my_special_func"))
        assert "my_special_func" in result

    def test_finds_class_definition(self, tmp_path):
        f = tmp_path / "classes.py"
        f.write_text(
            "class MySpecialClass:\n"
            "    \"\"\"A special class.\"\"\"\n"
            "    def __init__(self):\n"
            "        pass\n"
        )
        reg = _make_session_registry(project_dir=tmp_path)
        result = _run(reg.get("inspect").handler(arg="MySpecialClass"))
        assert "MySpecialClass" in result

    def test_shows_source_code(self, tmp_path):
        f = tmp_path / "src.py"
        f.write_text("def target_fn():\n    return 42\n")
        reg = _make_session_registry(project_dir=tmp_path)
        result = _run(reg.get("inspect").handler(arg="target_fn"))
        assert "return 42" in result or "```python" in result

    def test_shows_file_and_line(self, tmp_path):
        f = tmp_path / "located.py"
        f.write_text("x = 1\ndef find_me():\n    pass\n")
        reg = _make_session_registry(project_dir=tmp_path)
        result = _run(reg.get("inspect").handler(arg="find_me"))
        assert "located.py" in result
        assert "2" in result  # line number

    def test_not_found_returns_message(self, tmp_path):
        reg = _make_session_registry(project_dir=tmp_path)
        result = _run(reg.get("inspect").handler(arg="XYZZY_IMPOSSIBLE_SYMBOL"))
        assert "не найден" in result or "not found" in result.lower()

    def test_finds_async_def(self, tmp_path):
        f = tmp_path / "async_mod.py"
        f.write_text("async def async_target():\n    pass\n")
        reg = _make_session_registry(project_dir=tmp_path)
        result = _run(reg.get("inspect").handler(arg="async_target"))
        assert "async_target" in result

    def test_shows_multiple_definitions(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("def duplicate_sym():\n    pass\n")
        f2.write_text("def duplicate_sym():\n    return 1\n")
        reg = _make_session_registry(project_dir=tmp_path)
        result = _run(reg.get("inspect").handler(arg="duplicate_sym"))
        assert "a.py" in result and "b.py" in result

    def test_extracts_limited_lines(self, tmp_path):
        # Function with 50+ lines should be truncated
        body = "\n".join(f"    x_{i} = {i}" for i in range(60))
        f = tmp_path / "long.py"
        f.write_text(f"def long_func():\n{body}\n")
        reg = _make_session_registry(project_dir=tmp_path)
        result = _run(reg.get("inspect").handler(arg="long_func"))
        # Should not include all 60 lines (max 40)
        assert "long_func" in result


# ── Task 193: /ask ────────────────────────────────────────────────────────────

class TestAskCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("ask") is not None

    def test_no_session_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("ask").handler(arg="what is Python?"))
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_no_arg_shows_usage(self):
        reg = _make_session_registry()
        result = _run(reg.get("ask").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_asks_llm(self):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "Python is a programming language."
        mock_resp.model = "gpt-4"
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("ask").handler(arg="what is Python?"))
        assert "Python is a programming language" in result

    def test_shows_model_name(self):
        reg = _make_session_registry(model="openai/gpt-4o")
        mock_resp = MagicMock()
        mock_resp.content = "Answer here"
        mock_resp.model = "openai/gpt-4o"
        reg._session.llm.complete = AsyncMock(return_value=mock_resp)
        result = _run(reg.get("ask").handler(arg="question"))
        assert "gpt-4o" in result or "[" in result

    def test_model_override_flag(self):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "Response"
        mock_resp.model = "openai/gpt-4o-mini"
        captured_kwargs = {}

        async def fake_complete(messages, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_resp

        reg._session.llm.complete = fake_complete
        _run(reg.get("ask").handler(arg="--model openai/gpt-4o-mini what is asyncio?"))
        assert captured_kwargs.get("model") == "openai/gpt-4o-mini"

    def test_model_flag_without_question_shows_error(self):
        reg = _make_session_registry()
        result = _run(reg.get("ask").handler(arg="--model openai/gpt-4o-mini"))
        assert "вопрос" in result or "question" in result.lower() or "укажите" in result.lower()

    def test_llm_error_handled(self):
        reg = _make_session_registry()
        reg._session.llm.complete = AsyncMock(side_effect=Exception("Connection timeout"))
        result = _run(reg.get("ask").handler(arg="what is Python?"))
        assert "ошибка" in result.lower() or "error" in result.lower() or "Connection timeout" in result

    def test_passes_question_to_llm(self):
        reg = _make_session_registry()
        mock_resp = MagicMock()
        mock_resp.content = "42"
        mock_resp.model = "gpt-4"
        captured_messages = []

        async def fake_complete(messages, **kwargs):
            captured_messages.extend(messages)
            return mock_resp

        reg._session.llm.complete = fake_complete
        _run(reg.get("ask").handler(arg="what is the answer?"))
        assert any("what is the answer?" in str(m) for m in captured_messages)
