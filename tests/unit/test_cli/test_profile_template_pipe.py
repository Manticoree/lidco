"""Tests for /profile (#182), /template (#183), /pipe (#184)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from lidco.cli.commands import CommandRegistry


def _run(coro) -> str:
    return asyncio.run(coro)


def _make_registry() -> CommandRegistry:
    return CommandRegistry()


def _make_session_registry(agents=None, **kwargs) -> CommandRegistry:
    reg = _make_registry()
    sess = MagicMock()
    orch = MagicMock()
    orch._conversation_history = kwargs.get("history", [])

    agent_reg = MagicMock()
    agent_reg.list_names.return_value = agents or ["coder", "tester", "debugger"]
    sess.agent_registry = agent_reg
    sess.orchestrator = orch
    reg.set_session(sess)
    return reg


# ── Task 182: /profile ────────────────────────────────────────────────────────

class TestProfileCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("profile") is not None

    def test_default_agent_stats_empty(self):
        reg = _make_registry()
        assert reg._agent_stats == {}

    def test_no_stats_shows_message(self):
        reg = _make_registry()
        result = _run(reg.get("profile").handler())
        assert "недоступна" in result or "no" in result.lower() or "пока" in result

    def test_shows_all_agents(self):
        reg = _make_registry()
        reg._agent_stats = {
            "coder": {"calls": 3, "tokens": 1500, "elapsed": 9.0},
            "tester": {"calls": 1, "tokens": 500, "elapsed": 2.0},
        }
        result = _run(reg.get("profile").handler())
        assert "coder" in result
        assert "tester" in result

    def test_shows_call_count(self):
        reg = _make_registry()
        reg._agent_stats = {"coder": {"calls": 5, "tokens": 2000, "elapsed": 10.0}}
        result = _run(reg.get("profile").handler())
        assert "5" in result

    def test_shows_tokens(self):
        reg = _make_registry()
        reg._agent_stats = {"coder": {"calls": 1, "tokens": 1500, "elapsed": 3.0}}
        result = _run(reg.get("profile").handler())
        assert "1500" in result or "1.5k" in result

    def test_shows_elapsed(self):
        reg = _make_registry()
        reg._agent_stats = {"coder": {"calls": 2, "tokens": 800, "elapsed": 6.4}}
        result = _run(reg.get("profile").handler())
        assert "6.4" in result

    def test_single_agent_detail(self):
        reg = _make_registry()
        reg._agent_stats = {"coder": {"calls": 4, "tokens": 2000, "elapsed": 8.0}}
        result = _run(reg.get("profile").handler(arg="coder"))
        assert "coder" in result
        assert "4" in result
        assert "2.0" in result  # avg time: 8/4

    def test_single_agent_not_found(self):
        reg = _make_registry()
        reg._agent_stats = {"coder": {"calls": 1, "tokens": 100, "elapsed": 1.0}}
        result = _run(reg.get("profile").handler(arg="ghost"))
        assert "не найден" in result or "not found" in result.lower()

    def test_single_agent_shows_available(self):
        reg = _make_registry()
        reg._agent_stats = {"coder": {"calls": 1, "tokens": 100, "elapsed": 1.0}}
        result = _run(reg.get("profile").handler(arg="ghost"))
        assert "coder" in result

    def test_reset_clears_stats(self):
        reg = _make_registry()
        reg._agent_stats = {"coder": {"calls": 3, "tokens": 1500, "elapsed": 9.0}}
        _run(reg.get("profile").handler(arg="reset"))
        assert reg._agent_stats == {}

    def test_reset_returns_confirmation(self):
        reg = _make_registry()
        reg._agent_stats = {"coder": {"calls": 1, "tokens": 100, "elapsed": 1.0}}
        result = _run(reg.get("profile").handler(arg="reset"))
        assert "сброшена" in result or "reset" in result.lower()

    def test_sorted_by_tokens_desc(self):
        reg = _make_registry()
        reg._agent_stats = {
            "tester": {"calls": 1, "tokens": 100, "elapsed": 1.0},
            "coder": {"calls": 5, "tokens": 5000, "elapsed": 15.0},
        }
        result = _run(reg.get("profile").handler())
        # coder has more tokens, should appear first
        assert result.index("coder") < result.index("tester")


# ── Task 183: /template ───────────────────────────────────────────────────────

class TestTemplateCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("template") is not None

    def test_default_templates_empty(self):
        reg = _make_registry()
        assert reg._templates == {}

    def test_no_arg_shows_empty_message(self):
        reg = _make_registry()
        result = _run(reg.get("template").handler())
        assert "не определены" in result or "no" in result.lower() or "empty" in result.lower()

    def test_save_template(self):
        reg = _make_registry()
        _run(reg.get("template").handler(arg="save fix Fix the bug in {{FILE}}"))
        assert "fix" in reg._templates
        assert "{{FILE}}" in reg._templates["fix"]

    def test_save_returns_confirmation(self):
        reg = _make_registry()
        result = _run(reg.get("template").handler(arg="save review Review {{FILE}} for issues"))
        assert "review" in result or "сохранён" in result.lower()

    def test_save_shows_placeholders(self):
        reg = _make_registry()
        result = _run(reg.get("template").handler(arg="save tmpl Do {{ACTION}} in {{FILE}}"))
        assert "ACTION" in result or "FILE" in result

    def test_list_shows_templates(self):
        reg = _make_registry()
        reg._templates = {"fix": "Fix {{FILE}}", "review": "Review code"}
        result = _run(reg.get("template").handler(arg="list"))
        assert "fix" in result
        assert "review" in result

    def test_use_with_vars(self):
        reg = _make_registry()
        reg._templates["fix"] = "Fix the bug in {{FILE}}"
        reg._vars["FILE"] = "auth.py"
        result = _run(reg.get("template").handler(arg="use fix"))
        assert result.startswith("__RETRY__:Fix the bug in auth.py")

    def test_use_with_inline_override(self):
        reg = _make_registry()
        reg._templates["fix"] = "Fix {{FILE}}"
        result = _run(reg.get("template").handler(arg="use fix FILE=main.py"))
        assert result.startswith("__RETRY__:Fix main.py")

    def test_use_unfilled_placeholders_warns(self):
        reg = _make_registry()
        reg._templates["tmpl"] = "Do {{ACTION}} in {{FILE}}"
        result = _run(reg.get("template").handler(arg="use tmpl"))
        assert "ACTION" in result or "FILE" in result
        assert "__RETRY__" not in result

    def test_use_nonexistent_template(self):
        reg = _make_registry()
        result = _run(reg.get("template").handler(arg="use ghost"))
        assert "не найден" in result or "not found" in result.lower()

    def test_del_removes_template(self):
        reg = _make_registry()
        reg._templates["old"] = "text"
        _run(reg.get("template").handler(arg="del old"))
        assert "old" not in reg._templates

    def test_del_nonexistent_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("template").handler(arg="del ghost"))
        assert "не найден" in result or "not found" in result.lower()

    def test_show_displays_raw_template(self):
        reg = _make_registry()
        reg._templates["tmpl"] = "Fix {{FILE}} carefully"
        result = _run(reg.get("template").handler(arg="show tmpl"))
        assert "Fix {{FILE}} carefully" in result

    def test_clear_removes_all(self):
        reg = _make_registry()
        reg._templates = {"a": "x", "b": "y"}
        _run(reg.get("template").handler(arg="clear"))
        assert reg._templates == {}

    def test_invalid_name_rejected(self):
        reg = _make_registry()
        result = _run(reg.get("template").handler(arg="save my-template! text"))
        # "!" is invalid
        assert "недопустим" in result.lower() or "invalid" in result.lower()

    def test_use_shows_available_when_not_found(self):
        reg = _make_registry()
        reg._templates["fix"] = "Fix {{FILE}}"
        result = _run(reg.get("template").handler(arg="use ghost"))
        assert "fix" in result


# ── Task 184: /pipe ───────────────────────────────────────────────────────────

class TestPipeCommand:
    def test_registered(self):
        reg = _make_registry()
        assert reg.get("pipe") is not None

    def test_no_arg_shows_usage(self):
        reg = _make_registry()
        result = _run(reg.get("pipe").handler())
        assert "использование" in result.lower() or "usage" in result.lower()

    def test_no_session_shows_error(self):
        reg = _make_registry()
        result = _run(reg.get("pipe").handler(arg="coder | tester write a function"))
        assert "не инициализирована" in result or "not initialized" in result.lower()

    def test_single_segment_shows_error(self):
        reg = _make_session_registry()
        result = _run(reg.get("pipe").handler(arg="coder write a function"))
        assert "хотя бы" in result or "least" in result.lower() or "|" in result

    def test_unknown_agent_shows_error(self):
        reg = _make_session_registry(agents=["coder"])
        result = _run(reg.get("pipe").handler(arg="coder | ghost write something"))
        assert "ghost" in result or "не найден" in result

    def test_pipe_two_agents(self):
        reg = _make_session_registry()
        resp1 = MagicMock()
        resp1.content = "Code written"
        resp2 = MagicMock()
        resp2.content = "Tests passed"
        reg._session.orchestrator.handle = AsyncMock(side_effect=[resp1, resp2])

        result = _run(reg.get("pipe").handler(arg="coder | tester write a sort function"))
        assert "coder" in result
        assert "tester" in result

    def test_pipe_passes_output_to_next(self):
        reg = _make_session_registry()
        resp1 = MagicMock()
        resp1.content = "def sort(lst): return sorted(lst)"
        resp2 = MagicMock()
        resp2.content = "All tests pass"

        calls = []
        async def fake_handle(msg, agent_name=None, **kw):
            calls.append((agent_name, msg))
            return resp1 if agent_name == "coder" else resp2

        reg._session.orchestrator.handle = fake_handle
        _run(reg.get("pipe").handler(arg="coder | tester write sort"))

        # Second agent should receive first agent's output
        assert calls[1][1] == "def sort(lst): return sorted(lst)"

    def test_pipe_three_agents(self):
        reg = _make_session_registry()
        responses = [MagicMock(content=f"output{i}") for i in range(3)]
        reg._session.orchestrator.handle = AsyncMock(side_effect=responses)

        result = _run(reg.get("pipe").handler(arg="coder | debugger | tester write code"))
        assert "coder" in result
        assert "debugger" in result
        assert "tester" in result

    def test_pipe_shows_step_numbers(self):
        reg = _make_session_registry()
        resp = MagicMock(content="done")
        reg._session.orchestrator.handle = AsyncMock(return_value=resp)
        result = _run(reg.get("pipe").handler(arg="coder | tester hello"))
        assert "Шаг 1" in result or "Step 1" in result.lower() or "1" in result

    def test_no_message_shows_error(self):
        reg = _make_session_registry()
        result = _run(reg.get("pipe").handler(arg="coder | tester"))
        assert "сообщение" in result or "message" in result.lower()

    def test_pipe_shows_pipeline_header(self):
        reg = _make_session_registry()
        resp = MagicMock(content="result")
        reg._session.orchestrator.handle = AsyncMock(return_value=resp)
        result = _run(reg.get("pipe").handler(arg="coder | tester do something"))
        assert "coder" in result and "tester" in result and ("→" in result or "->" in result or "Pipe" in result)
