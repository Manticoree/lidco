"""Tests for the QA agent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lidco.agents.builtin.qa import QA_SYSTEM_PROMPT, create_qa_agent
from lidco.agents.base import BaseAgent


def _make_qa() -> BaseAgent:
    llm = MagicMock()
    registry = MagicMock()
    registry.list_tools.return_value = []
    registry.get.return_value = None
    return create_qa_agent(llm, registry)


class TestQAAgentCreation:
    def test_returns_base_agent(self):
        agent = _make_qa()
        assert isinstance(agent, BaseAgent)

    def test_name_is_qa(self):
        agent = _make_qa()
        assert agent.name == "qa"

    def test_description_mentions_validation(self):
        agent = _make_qa()
        assert "validation" in agent.description.lower()

    def test_has_required_tools(self):
        agent = _make_qa()
        expected = {"file_read", "file_write", "file_edit", "bash", "glob", "grep", "git"}
        assert expected == set(agent.config.tools)

    def test_temperature_is_low(self):
        agent = _make_qa()
        assert agent.config.temperature <= 0.1

    def test_get_system_prompt_returns_prompt(self):
        agent = _make_qa()
        assert agent.get_system_prompt() == QA_SYSTEM_PROMPT


class TestQASystemPrompt:
    def test_mentions_compilation_check(self):
        assert "compilation" in QA_SYSTEM_PROMPT.lower() or "import" in QA_SYSTEM_PROMPT.lower()

    def test_mentions_tests(self):
        assert "test" in QA_SYSTEM_PROMPT.lower()

    def test_mentions_pytest(self):
        assert "pytest" in QA_SYSTEM_PROMPT.lower()

    def test_mentions_git_diff(self):
        assert "git diff" in QA_SYSTEM_PROMPT.lower()

    def test_has_three_phases(self):
        assert "Phase 1" in QA_SYSTEM_PROMPT
        assert "Phase 2" in QA_SYSTEM_PROMPT
        assert "Phase 3" in QA_SYSTEM_PROMPT

    def test_mentions_fix_failures(self):
        assert "fail" in QA_SYSTEM_PROMPT.lower()
