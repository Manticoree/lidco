"""Researcher agent — web search and analysis specialist."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

RESEARCHER_SYSTEM_PROMPT = """\
You are LIDCO Researcher, a web search and analysis specialist.

## Output Format
### Findings — bullet points with code examples.
### Sources — URLs with brief descriptions.
### Recommendations — actionable, with trade-offs.

## Guidelines
- Cite sources. Prefer official docs. Present pros/cons for alternatives.
"""


def create_researcher_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the researcher agent."""
    config = AgentConfig(
        name="researcher",
        description="Web research and analysis.",
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        temperature=0.2,
        tools=["web_search", "web_fetch", "file_read", "glob", "grep", "file_write", "ask_user"],
        max_iterations=200,
    )

    class ResearcherAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return RESEARCHER_SYSTEM_PROMPT

    return ResearcherAgent(config=config, llm=llm, tool_registry=tool_registry)
