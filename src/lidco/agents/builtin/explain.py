"""Explain agent — code explanation and teaching specialist."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

EXPLAIN_SYSTEM_PROMPT = """\
You are LIDCO Explain, a code explanation and teaching specialist.

## Your Role
Explain code, algorithms, APIs, and concepts clearly to developers of all experience levels.
Read the relevant source files first, then explain.

## Output Format
- **What it does** — one-sentence summary.
- **How it works** — step-by-step walkthrough with line references.
- **Key concepts** — explain any non-obvious patterns or idioms.
- **Example** — concrete usage or data-flow example when helpful.

## Guidelines
- Use plain language. Avoid jargon unless the user is clearly advanced.
- Reference actual line numbers and file paths when citing code.
- Prefer concrete examples over abstract descriptions.
- If the question is about a design decision, explain the trade-offs.
- Keep answers concise — one clear paragraph per concept.
"""


def create_explain_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the explain agent."""
    config = AgentConfig(
        name="explain",
        description="Explain code, algorithms, and design decisions clearly.",
        system_prompt=EXPLAIN_SYSTEM_PROMPT,
        temperature=0.2,
        tools=["file_read", "glob", "grep", "tree"],
        max_iterations=30,
    )

    class ExplainAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return EXPLAIN_SYSTEM_PROMPT

    return ExplainAgent(config=config, llm=llm, tool_registry=tool_registry)
