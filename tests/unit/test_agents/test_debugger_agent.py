"""Tests for Task #63: Enhanced DebuggerAgent system prompt and routing."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lidco.agents.builtin.debugger import DEBUGGER_SYSTEM_PROMPT, create_debugger_agent
from lidco.agents.graph import ROUTER_PROMPT
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_agent():
    llm = MagicMock(spec=BaseLLMProvider)
    registry = ToolRegistry()
    return create_debugger_agent(llm, registry)


# ── System prompt content ─────────────────────────────────────────────────────


class TestDebuggerSystemPrompt:
    """The DEBUGGER_SYSTEM_PROMPT must contain all six phases."""

    def test_phase_1_collect_evidence(self):
        assert "Phase 1" in DEBUGGER_SYSTEM_PROMPT
        assert "Collect Evidence" in DEBUGGER_SYSTEM_PROMPT

    def test_phase_2_parse_traceback(self):
        assert "Phase 2" in DEBUGGER_SYSTEM_PROMPT
        assert "bottom-to-top" in DEBUGGER_SYSTEM_PROMPT.lower() or "bottom" in DEBUGGER_SYSTEM_PROMPT

    def test_phase_3_error_taxonomy(self):
        assert "Phase 3" in DEBUGGER_SYSTEM_PROMPT
        assert "Taxonomy" in DEBUGGER_SYSTEM_PROMPT or "taxonomy" in DEBUGGER_SYSTEM_PROMPT.lower()

    def test_phase_4_isolate(self):
        assert "Phase 4" in DEBUGGER_SYSTEM_PROMPT
        assert "Isolate" in DEBUGGER_SYSTEM_PROMPT or "isolate" in DEBUGGER_SYSTEM_PROMPT.lower()

    def test_phase_5_fix(self):
        assert "Phase 5" in DEBUGGER_SYSTEM_PROMPT
        assert "Fix" in DEBUGGER_SYSTEM_PROMPT

    def test_phase_6_verify(self):
        assert "Phase 6" in DEBUGGER_SYSTEM_PROMPT
        assert "Verify" in DEBUGGER_SYSTEM_PROMPT or "verify" in DEBUGGER_SYSTEM_PROMPT.lower()

    def test_error_taxonomy_keywords(self):
        prompt = DEBUGGER_SYSTEM_PROMPT
        assert "AttributeError" in prompt
        assert "TypeError" in prompt
        assert "ImportError" in prompt
        assert "KeyError" in prompt
        assert "AssertionError" in prompt
        assert "RecursionError" in prompt
        assert "RuntimeError" in prompt

    def test_references_file_edit_tool(self):
        assert "file_edit" in DEBUGGER_SYSTEM_PROMPT

    def test_references_run_tests_or_pytest(self):
        assert "run_tests" in DEBUGGER_SYSTEM_PROMPT or "pytest" in DEBUGGER_SYSTEM_PROMPT

    def test_references_grep(self):
        assert "grep" in DEBUGGER_SYSTEM_PROMPT

    def test_references_file_read(self):
        assert "file_read" in DEBUGGER_SYSTEM_PROMPT

    def test_mentions_recent_errors_section(self):
        assert "## Recent Errors" in DEBUGGER_SYSTEM_PROMPT

    def test_mentions_traceback_bottom_to_top(self):
        assert "bottom" in DEBUGGER_SYSTEM_PROMPT.lower()


# ── build_system_prompt ───────────────────────────────────────────────────────


class TestDebuggerBuildSystemPrompt:
    def test_no_context_no_stream(self):
        agent = _make_agent()
        prompt = agent.build_system_prompt()
        assert DEBUGGER_SYSTEM_PROMPT in prompt
        assert "## Current Context" not in prompt

    def test_with_context_appended(self):
        agent = _make_agent()
        prompt = agent.build_system_prompt(context="some context here")
        assert "## Current Context" in prompt
        assert "some context here" in prompt

    def test_streaming_narration_added_when_callback_set(self):
        from lidco.agents.base import _STREAMING_NARRATION_PROMPT
        agent = _make_agent()
        agent.set_stream_callback(lambda x: None)
        prompt = agent.build_system_prompt()
        assert "Streaming Style" in prompt or _STREAMING_NARRATION_PROMPT in prompt

    def test_no_clarification_hint_without_ask_user_tool(self):
        """DebuggerAgent overrides build_system_prompt — no clarification hint added."""
        agent = _make_agent()
        prompt = agent.build_system_prompt()
        # The overridden build_system_prompt does not append _CLARIFICATION_HINT
        assert "## Clarification" not in prompt


# ── ROUTER_PROMPT keywords ────────────────────────────────────────────────────


class TestRouterPromptKeywords:
    def test_traceback_routes_to_debugger(self):
        assert "traceback" in ROUTER_PROMPT.lower()

    def test_exception_routes_to_debugger(self):
        assert "exception" in ROUTER_PROMPT.lower()

    def test_attributeerror_routes_to_debugger(self):
        assert "attributeerror" in ROUTER_PROMPT.lower()

    def test_typeerror_routes_to_debugger(self):
        assert "typeerror" in ROUTER_PROMPT.lower()

    def test_importerror_routes_to_debugger(self):
        assert "importerror" in ROUTER_PROMPT.lower()

    def test_keyerror_routes_to_debugger(self):
        assert "keyerror" in ROUTER_PROMPT.lower()

    def test_stack_trace_routes_to_debugger(self):
        assert "stack trace" in ROUTER_PROMPT.lower()

    def test_original_bug_keyword_still_present(self):
        assert "bug" in ROUTER_PROMPT.lower()
