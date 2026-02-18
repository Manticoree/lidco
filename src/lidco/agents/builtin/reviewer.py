"""Reviewer Agent - code review specialist."""

from __future__ import annotations

from lidco.agents.base import AgentConfig, BaseAgent
from lidco.llm.base import BaseLLMProvider
from lidco.tools.registry import ToolRegistry

REVIEWER_SYSTEM_PROMPT = """\
You are LIDCO Reviewer, an expert code reviewer.

## Checklist
No secrets, input validation, error handling, no mutation, functions <50 lines, files <800 lines, clear naming, no dead code, security (injection/XSS/CSRF).

## Severity
CRITICAL: security, data loss | HIGH: bugs, missing error handling | MEDIUM: quality | LOW: style

## Output
For each finding: file:line, severity, description, suggested fix.
"""


def create_reviewer_agent(llm: BaseLLMProvider, tool_registry: ToolRegistry) -> BaseAgent:
    """Create the reviewer agent."""
    config = AgentConfig(
        name="reviewer",
        description="Code review: quality, security.",
        system_prompt=REVIEWER_SYSTEM_PROMPT,
        temperature=0.1,
        tools=["file_read", "glob", "grep"],
        max_iterations=200,
    )

    class ReviewerAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return REVIEWER_SYSTEM_PROMPT

    return ReviewerAgent(config=config, llm=llm, tool_registry=tool_registry)
