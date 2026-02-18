"""Refactor Agent - code refactoring and cleanup."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

REFACTOR_SYSTEM_PROMPT = """\
You are LIDCO Refactor, an expert code refactoring assistant.

## Guidelines
- ALWAYS preserve existing behavior. Small incremental steps.
- Run tests after each change. Read full context before modifying.
- Immutable patterns, functions <50 lines, files <800 lines, nesting <4 levels.
- Remove dead code, console.log, hardcoded values.

## Response Style
- Explain rationale before changes. Show before/after for significant changes.
- List affected files. Confirm tests pass after each step.
"""


def create_refactor_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the refactor agent for code cleanup and restructuring."""
    config = AgentConfig(
        name="refactor",
        description="Code refactoring and cleanup.",
        system_prompt=REFACTOR_SYSTEM_PROMPT,
        temperature=0.1,
        max_iterations=200,
    )

    class RefactorAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return REFACTOR_SYSTEM_PROMPT

    return RefactorAgent(config=config, llm=llm, tool_registry=tool_registry)
