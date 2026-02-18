"""Doc Agent - documentation generation and maintenance."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

DOCS_SYSTEM_PROMPT = """\
You are LIDCO Docs, a technical documentation assistant.

## Guidelines
- Clear, concise, actionable docs. Include code examples.
- Document "why" not just "what". Keep docstrings in sync with code.
- Use Google-style docstrings (Args, Returns, Raises).
- Write for the audience: API docs for consumers, internal docs for maintainers.
"""


def create_docs_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the docs agent for documentation generation and maintenance."""
    config = AgentConfig(
        name="docs",
        description="Documentation generation.",
        system_prompt=DOCS_SYSTEM_PROMPT,
        temperature=0.3,
        max_iterations=200,
        tools=["file_read", "file_write", "file_edit", "glob", "grep"],
    )

    class DocAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return DOCS_SYSTEM_PROMPT

    return DocAgent(config=config, llm=llm, tool_registry=tool_registry)
