"""Architect Agent - system design and architecture decisions."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

ARCHITECT_SYSTEM_PROMPT = """\
You are LIDCO Architect, an expert software architecture assistant.

## Guidelines
- Analyze existing codebase before recommendations.
- Weigh trade-offs: performance, maintainability, complexity.
- Prefer simple proven patterns. Recommend incremental improvements.

## Response Style
- Structured analysis. Pros/cons for options. Clear recommendation with reasoning.
- Use ASCII/Mermaid diagrams when helpful. Reference specific files.
"""


def create_architect_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the architect agent for system design decisions."""
    config = AgentConfig(
        name="architect",
        description="System design and architecture.",
        system_prompt=ARCHITECT_SYSTEM_PROMPT,
        temperature=0.2,
        max_iterations=200,
        tools=["file_read", "glob", "grep", "ask_user"],
    )

    class ArchitectAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return ARCHITECT_SYSTEM_PROMPT

    return ArchitectAgent(config=config, llm=llm, tool_registry=tool_registry)
