"""Tests for the /pr slash command."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.cli.commands import CommandRegistry
from lidco.tools.base import ToolResult


def _make_session(*, active_pr_context: str | None = None) -> SimpleNamespace:
    orchestrator = MagicMock()
    orchestrator._conversation_history = []
    config = SimpleNamespace(llm=SimpleNamespace(default_model="openai/glm-4.7"))
    token_budget = SimpleNamespace(
        total_prompt_tokens=0, total_completion_tokens=0, total_cost_usd=0.0
    )
    return SimpleNamespace(
        orchestrator=orchestrator,
        config=config,
        token_budget=token_budget,
        active_pr_context=active_pr_context,
    )


@pytest.fixture()
def registry() -> CommandRegistry:
    return CommandRegistry()


# ---------------------------------------------------------------------------
# No session
# ---------------------------------------------------------------------------

class TestPrNoSession:
    @pytest.mark.asyncio
    async def test_no_session_returns_error(self, registry: CommandRegistry) -> None:
        result = await registry.get("pr").handler(arg="42")
        assert result == "Session not initialized."

    @pytest.mark.asyncio
    async def test_no_session_no_arg(self, registry: CommandRegistry) -> None:
        result = await registry.get("pr").handler()
        assert result == "Session not initialized."


# ---------------------------------------------------------------------------
# No arg (show usage / active PR preview)
# ---------------------------------------------------------------------------

class TestPrNoArg:
    @pytest.mark.asyncio
    async def test_no_arg_no_active_shows_usage(self, registry: CommandRegistry) -> None:
        registry.set_session(_make_session())
        result = await registry.get("pr").handler()
        assert "/pr <number>" in result or "Usage" in result

    @pytest.mark.asyncio
    async def test_no_arg_with_active_shows_preview(self, registry: CommandRegistry) -> None:
        session = _make_session(active_pr_context="## PR #10: My PR\n\nSome content.")
        registry.set_session(session)
        result = await registry.get("pr").handler()
        assert "PR #10" in result or "My PR" in result
        assert "/pr close" in result


# ---------------------------------------------------------------------------
# /pr close | /pr clear
# ---------------------------------------------------------------------------

class TestPrClose:
    @pytest.mark.asyncio
    async def test_close_clears_context(self, registry: CommandRegistry) -> None:
        session = _make_session(active_pr_context="## PR #10: Something")
        registry.set_session(session)
        result = await registry.get("pr").handler(arg="close")
        assert session.active_pr_context is None
        assert "cleared" in result.lower()

    @pytest.mark.asyncio
    async def test_clear_is_alias_for_close(self, registry: CommandRegistry) -> None:
        session = _make_session(active_pr_context="## PR #10: Something")
        registry.set_session(session)
        result = await registry.get("pr").handler(arg="clear")
        assert session.active_pr_context is None
        assert "cleared" in result.lower()

    @pytest.mark.asyncio
    async def test_close_when_no_context_still_succeeds(self, registry: CommandRegistry) -> None:
        session = _make_session()
        registry.set_session(session)
        result = await registry.get("pr").handler(arg="close")
        assert "cleared" in result.lower()


# ---------------------------------------------------------------------------
# /pr <number> — fetch PR
# ---------------------------------------------------------------------------

_MOCK_PR_OUTPUT = "## PR #42: Add feature\n\n**Branch:** `feature` → `main`"

_MOCK_PR_META = {
    "number": 42,
    "title": "Add feature",
    "state": "OPEN",
    "files_count": 3,
    "additions": 100,
    "deletions": 20,
}


def _mock_tool_success() -> MagicMock:
    tool = MagicMock()
    tool.execute = AsyncMock(
        return_value=ToolResult(
            output=_MOCK_PR_OUTPUT,
            success=True,
            metadata=_MOCK_PR_META,
        )
    )
    return tool


def _mock_tool_failure(error: str = "gh CLI not installed") -> MagicMock:
    tool = MagicMock()
    tool.execute = AsyncMock(
        return_value=ToolResult(output="", success=False, error=error)
    )
    return tool


class TestPrFetch:
    @pytest.mark.asyncio
    async def test_success_stores_context_in_session(self, registry: CommandRegistry) -> None:
        session = _make_session()
        registry.set_session(session)

        mock_tool = _mock_tool_success()
        with patch("lidco.tools.gh_pr.GHPRTool", return_value=mock_tool):
            result = await registry.get("pr").handler(arg="42")

        assert session.active_pr_context == _MOCK_PR_OUTPUT
        assert "42" in result
        assert "Add feature" in result

    @pytest.mark.asyncio
    async def test_failure_does_not_store_context(self, registry: CommandRegistry) -> None:
        session = _make_session()
        registry.set_session(session)

        mock_tool = _mock_tool_failure("gh CLI not installed")
        with patch("lidco.tools.gh_pr.GHPRTool", return_value=mock_tool):
            result = await registry.get("pr").handler(arg="999")

        assert session.active_pr_context is None
        assert "Failed" in result or "failed" in result

    @pytest.mark.asyncio
    async def test_success_result_contains_title_and_file_count(
        self, registry: CommandRegistry
    ) -> None:
        session = _make_session()
        registry.set_session(session)

        mock_tool = _mock_tool_success()
        with patch("lidco.tools.gh_pr.GHPRTool", return_value=mock_tool):
            result = await registry.get("pr").handler(arg="42")

        assert "Add feature" in result
        assert "3" in result  # files_count

    @pytest.mark.asyncio
    async def test_success_mentions_pr_close(self, registry: CommandRegistry) -> None:
        session = _make_session()
        registry.set_session(session)

        mock_tool = _mock_tool_success()
        with patch("lidco.tools.gh_pr.GHPRTool", return_value=mock_tool):
            result = await registry.get("pr").handler(arg="42")

        assert "/pr close" in result

    @pytest.mark.asyncio
    async def test_fetch_then_close_clears_context(self, registry: CommandRegistry) -> None:
        session = _make_session()
        registry.set_session(session)

        mock_tool = _mock_tool_success()
        with patch("lidco.tools.gh_pr.GHPRTool", return_value=mock_tool):
            await registry.get("pr").handler(arg="42")

        assert session.active_pr_context is not None

        await registry.get("pr").handler(arg="close")
        assert session.active_pr_context is None
