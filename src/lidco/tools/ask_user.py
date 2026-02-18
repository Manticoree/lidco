"""Ask User tool - allows agents to ask clarifying questions during execution."""

from __future__ import annotations

from typing import Any

from lidco.core.clarification import ClarificationNeeded
from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class AskUserTool(BaseTool):
    """Tool that allows agents to ask the user clarifying questions.

    Instead of executing directly, this tool raises ClarificationNeeded
    which is caught by BaseAgent._execute_tool() and handled via a callback.
    """

    @property
    def name(self) -> str:
        return "ask_user"

    @property
    def description(self) -> str:
        return "Ask user a clarifying question."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="question",
                type="string",
                description="The question to ask the user.",
                required=True,
            ),
            ToolParameter(
                name="options",
                type="string",
                description="Comma-separated options (e.g. 'JWT, Session, OAuth2'). "
                "Leave empty for free-text answers.",
                required=False,
                default="",
            ),
            ToolParameter(
                name="context",
                type="string",
                description="Brief context explaining why this question matters.",
                required=False,
                default="",
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        """Raise ClarificationNeeded instead of executing directly."""
        question = kwargs.get("question", "")
        options_str = kwargs.get("options", "")
        context = kwargs.get("context", "")

        if not question:
            return ToolResult(
                output="",
                success=False,
                error="Question is required.",
            )

        options = [
            opt.strip() for opt in options_str.split(",") if opt.strip()
        ] if options_str else []

        raise ClarificationNeeded(
            question=question,
            options=options,
            context=context,
        )
