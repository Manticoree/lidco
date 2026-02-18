"""Tests for the researcher agent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lidco.agents.builtin.researcher import create_researcher_agent


class TestResearcherAgent:
    def setup_method(self):
        self.llm = MagicMock()
        self.tool_registry = MagicMock()
        self.agent = create_researcher_agent(self.llm, self.tool_registry)

    def test_name(self):
        assert self.agent.name == "researcher"

    def test_description(self):
        assert "search" in self.agent.description.lower() or "research" in self.agent.description.lower()

    def test_tools(self):
        expected_tools = {"web_search", "web_fetch", "file_read", "glob", "grep", "file_write", "ask_user"}
        assert set(self.agent.config.tools) == expected_tools

    def test_temperature(self):
        assert self.agent.config.temperature == 0.2

    def test_max_iterations(self):
        assert self.agent.config.max_iterations == 200

    def test_system_prompt_contains_key_sections(self):
        prompt = self.agent.get_system_prompt()
        assert "Findings" in prompt
        assert "Sources" in prompt
        assert "Recommendations" in prompt


class TestResearcherRegisteredInSession:
    def test_researcher_in_builtin_exports(self):
        from lidco.agents.builtin import __all__

        assert "create_researcher_agent" in __all__

    def test_researcher_factory_importable(self):
        from lidco.agents.builtin import create_researcher_agent as factory

        assert callable(factory)
