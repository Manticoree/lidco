"""Tests for the ask_user tool."""

import pytest

from lidco.core.clarification import ClarificationNeeded
from lidco.tools.ask_user import AskUserTool
from lidco.tools.base import ToolPermission


class TestAskUserTool:
    def test_name(self):
        tool = AskUserTool()
        assert tool.name == "ask_user"

    def test_description(self):
        tool = AskUserTool()
        assert "clarifying question" in tool.description

    def test_permission_is_auto(self):
        tool = AskUserTool()
        assert tool.permission == ToolPermission.AUTO

    def test_parameters(self):
        tool = AskUserTool()
        params = tool.parameters
        names = [p.name for p in params]
        assert "question" in names
        assert "options" in names
        assert "context" in names

        question_param = next(p for p in params if p.name == "question")
        assert question_param.required is True

        options_param = next(p for p in params if p.name == "options")
        assert options_param.required is False

    def test_openai_schema(self):
        tool = AskUserTool()
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "ask_user"
        props = schema["function"]["parameters"]["properties"]
        assert "question" in props
        assert "options" in props
        assert "context" in props
        assert "question" in schema["function"]["parameters"]["required"]

    @pytest.mark.asyncio
    async def test_raises_clarification_needed(self):
        tool = AskUserTool()
        with pytest.raises(ClarificationNeeded) as exc_info:
            await tool._run(
                question="Which database?",
                options="PostgreSQL, MySQL, SQLite",
                context="Need to choose a database",
            )
        assert exc_info.value.question == "Which database?"
        assert exc_info.value.options == ["PostgreSQL", "MySQL", "SQLite"]
        assert exc_info.value.context == "Need to choose a database"

    @pytest.mark.asyncio
    async def test_raises_with_empty_options(self):
        tool = AskUserTool()
        with pytest.raises(ClarificationNeeded) as exc_info:
            await tool._run(question="What name?")
        assert exc_info.value.options == []

    @pytest.mark.asyncio
    async def test_execute_catches_exception(self):
        """execute() wraps _run() errors, but ClarificationNeeded propagates."""
        tool = AskUserTool()
        # ClarificationNeeded is caught by execute() as a generic Exception
        # and returned as a ToolResult with error
        result = await tool.execute(question="Which DB?")
        assert result.success is False
        assert "Which DB?" in (result.error or "")

    @pytest.mark.asyncio
    async def test_empty_question_returns_error(self):
        tool = AskUserTool()
        result = await tool.execute(question="")
        assert result.success is False
        assert "required" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_options_parsing(self):
        tool = AskUserTool()
        with pytest.raises(ClarificationNeeded) as exc_info:
            await tool._run(
                question="Framework?",
                options="React, Vue, Svelte",
            )
        assert exc_info.value.options == ["React", "Vue", "Svelte"]

    @pytest.mark.asyncio
    async def test_options_with_whitespace(self):
        tool = AskUserTool()
        with pytest.raises(ClarificationNeeded) as exc_info:
            await tool._run(
                question="Q?",
                options=" A ,  B , C ",
            )
        assert exc_info.value.options == ["A", "B", "C"]
