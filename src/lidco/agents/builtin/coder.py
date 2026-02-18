"""Coder Agent - main coding assistant."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

CODER_SYSTEM_PROMPT = """\
You are LIDCO Coder, an expert software engineering assistant.

## Guidelines
- Read files before modifying. Prefer editing over creating.
- Immutable patterns, small functions (<50 lines), focused files (<800 lines).
- Handle errors, validate inputs, never hardcode secrets.

## Response Style
- Be concise and direct. Show reasoning. Explain what and why.
"""


def create_coder_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the default coder agent."""
    config = AgentConfig(
        name="coder",
        description="Code writing, debugging, modification.",
        system_prompt=CODER_SYSTEM_PROMPT,
        temperature=0.1,
        max_iterations=200,
    )

    class CoderAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return CODER_SYSTEM_PROMPT

    return CoderAgent(config=config, llm=llm, tool_registry=tool_registry)
