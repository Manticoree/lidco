"""Tester Agent - generating and running tests."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

TESTER_SYSTEM_PROMPT = """\
You are LIDCO Tester, an expert test engineering assistant.

## TDD Workflow
RED: write failing test → GREEN: minimal implementation → REFACTOR: improve keeping green.

## Guidelines
- pytest, 80%+ coverage. Test behavior not implementation.
- Isolated tests, descriptive names, fixtures for shared setup.
- Mock external deps. Parametrize for multiple inputs. Test edge cases.

## Response Style
- Show test code with explanations. Report results and coverage.
"""


def create_tester_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the tester agent for test generation and execution."""
    config = AgentConfig(
        name="tester",
        description="Test writing with TDD.",
        system_prompt=TESTER_SYSTEM_PROMPT,
        temperature=0.1,
        max_iterations=200,
        tools=["file_read", "file_write", "file_edit", "bash", "glob", "grep"],
    )

    class TestAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return TESTER_SYSTEM_PROMPT

    return TestAgent(config=config, llm=llm, tool_registry=tool_registry)
