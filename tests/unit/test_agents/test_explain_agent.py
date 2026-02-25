"""Tests for the Explain agent."""

from __future__ import annotations

from unittest.mock import MagicMock

from lidco.agents.base import BaseAgent
from lidco.agents.builtin.explain import EXPLAIN_SYSTEM_PROMPT, create_explain_agent


def _make_explain() -> BaseAgent:
    llm = MagicMock()
    registry = MagicMock()
    registry.list_tools.return_value = []
    registry.get.return_value = None
    return create_explain_agent(llm, registry)


class TestExplainAgentCreation:
    def test_returns_base_agent(self) -> None:
        assert isinstance(_make_explain(), BaseAgent)

    def test_name_is_explain(self) -> None:
        assert _make_explain().name == "explain"

    def test_description_mentions_explain(self) -> None:
        assert "explain" in _make_explain().description.lower()

    def test_tools_are_read_only(self) -> None:
        """Explain agent should not have write tools."""
        tools = set(_make_explain().config.tools)
        write_tools = {"file_write", "file_edit", "bash", "git"}
        assert not tools & write_tools

    def test_has_file_read_tool(self) -> None:
        assert "file_read" in _make_explain().config.tools

    def test_temperature_is_low(self) -> None:
        assert _make_explain().config.temperature <= 0.3

    def test_get_system_prompt_returns_prompt(self) -> None:
        assert _make_explain().get_system_prompt() == EXPLAIN_SYSTEM_PROMPT


class TestExplainSystemPrompt:
    def test_mentions_plain_language(self) -> None:
        assert "plain" in EXPLAIN_SYSTEM_PROMPT.lower()

    def test_has_output_format_section(self) -> None:
        assert "Output Format" in EXPLAIN_SYSTEM_PROMPT

    def test_mentions_examples(self) -> None:
        assert "example" in EXPLAIN_SYSTEM_PROMPT.lower()

    def test_mentions_what_it_does(self) -> None:
        assert "What it does" in EXPLAIN_SYSTEM_PROMPT
