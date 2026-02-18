"""Debugger Agent - error analysis and fix specialist."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

DEBUGGER_SYSTEM_PROMPT = """\
You are LIDCO Debugger, an expert at finding and fixing bugs.

## Process
1. Reproduce → 2. Isolate file/function → 3. Analyze logic → 4. Minimal fix → 5. Verify

## Guidelines
- Read code before suggesting fixes. Fix root cause, not symptoms.
- Minimal changes only. Check for related issues in nearby code.
"""


def create_debugger_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the debugger agent."""
    config = AgentConfig(
        name="debugger",
        description="Bug analysis and fixing.",
        system_prompt=DEBUGGER_SYSTEM_PROMPT,
        temperature=0.1,
        max_iterations=200,
    )

    class DebuggerAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return DEBUGGER_SYSTEM_PROMPT

    return DebuggerAgent(config=config, llm=llm, tool_registry=tool_registry)
