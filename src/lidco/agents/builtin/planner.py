"""Planner Agent - task decomposition and planning."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

PLANNER_SYSTEM_PROMPT = """\
You are LIDCO Planner, an expert at breaking down complex tasks.

Explore the codebase, then create a step-by-step implementation plan. Do NOT modify files.

## Output Format
End with `## Implementation Plan`:
1. [Easy/Medium/Hard] File `path` — what to do
2. ...

**Dependencies:** which steps depend on others.
**Risks:** potential issues or decisions needed.

## Guidelines
- Read-only: use file_read, grep, glob to explore.
- Consider existing patterns. Keep plans practical and incremental.
"""


def create_planner_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the planner agent."""
    config = AgentConfig(
        name="planner",
        description="Task decomposition and implementation planning.",
        system_prompt=PLANNER_SYSTEM_PROMPT,
        temperature=0.2,
        tools=["file_read", "glob", "grep", "ask_user"],  # read-only tools + clarification
        max_iterations=200,
    )

    class PlannerAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return PLANNER_SYSTEM_PROMPT

    return PlannerAgent(config=config, llm=llm, tool_registry=tool_registry)
