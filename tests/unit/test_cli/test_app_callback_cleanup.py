"""Regression tests: non-streaming mode must clear all callbacks after each turn.

Before the fix:
  Non-streaming `finally` block called set_status_callback(None) only.
  set_token_callback(None) was missing → stale token callback left on orchestrator
  between turns, causing spurious UI updates on the next request.

After the fix:
  Both set_status_callback(None) and set_token_callback(None) are called in finally.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_response():
    resp = MagicMock()
    resp.content = "done"
    resp.tool_calls_made = []
    resp.token_usage = MagicMock(
        total_tokens=10,
        prompt_tokens=6,
        completion_tokens=4,
        total_cost_usd=0.002,
    )
    return resp


def _make_mock_session(streaming: bool = False):
    """Build a minimal mock Session for run_repl tests."""
    orch = MagicMock()
    token_cb_calls: list = []
    status_cb_calls: list = []
    orch.set_token_callback.side_effect = lambda cb: token_cb_calls.append(cb)
    orch.set_status_callback.side_effect = lambda cb: status_cb_calls.append(cb)
    orch.handle = AsyncMock(return_value=_make_mock_response())
    orch._token_cb_calls = token_cb_calls
    orch._status_cb_calls = status_cb_calls

    session = MagicMock()
    session.orchestrator = orch
    session.debug_mode = False
    session.project_dir = Path("/tmp/test_project")
    session.get_full_context = MagicMock(return_value="")
    session.agent_registry.list_names = MagicMock(return_value=["coder"])
    session.token_budget.check_remaining = MagicMock()
    session.token_budget.total_tokens = 10
    session.token_budget.total_prompt_tokens = 6
    session.token_budget.total_completion_tokens = 4
    session.token_budget.total_cost_usd = 0.002

    config = MagicMock()
    config.llm.streaming = streaming
    config.llm.default_model = "test-model"
    config.cli.show_tool_calls = False
    config.agents.auto_review = True
    config.agents.auto_plan = True
    config.permissions = MagicMock()
    config.logging.format = "pretty"
    config.logging.level = "INFO"
    config.logging.log_file = None

    session.config = config
    return session, orch


async def _run_repl_one_turn(session: MagicMock, message: str = "hello world") -> None:
    """Run run_repl() with a single user message then exit."""
    prompt_mock = MagicMock()
    # run_repl uses prompt_session.prompt() (sync) inside run_in_executor, not prompt_async
    prompt_mock.prompt = MagicMock(side_effect=[message, EOFError()])

    live_ctx = MagicMock()
    live_ctx.__enter__ = MagicMock(return_value=live_ctx)
    live_ctx.__exit__ = MagicMock(return_value=False)

    with (
        patch("lidco.cli.app.Session", return_value=session),
        patch("lidco.cli.app.PromptSession", return_value=prompt_mock),
        patch("lidco.cli.app.Console"),
        patch("lidco.cli.app.Renderer"),
        patch("lidco.core.logging.setup_logging"),
        patch("lidco.core.rules.RulesManager.has_rules_file", return_value=True),
        patch("lidco.cli.app.Live", return_value=live_ctx),
    ):
        from lidco.cli.app import run_repl

        await run_repl()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNonStreamingCallbackCleanup:
    @pytest.mark.asyncio
    async def test_token_callback_cleared_after_turn(self) -> None:
        """set_token_callback(None) must be called after a non-streaming turn."""
        session, orch = _make_mock_session(streaming=False)
        await _run_repl_one_turn(session)

        # The final call must have been None
        assert orch._token_cb_calls, "set_token_callback was never called"
        assert orch._token_cb_calls[-1] is None, (
            "set_token_callback(None) not called — token callback leaked to next turn"
        )

    @pytest.mark.asyncio
    async def test_status_callback_cleared_after_turn(self) -> None:
        """set_status_callback(None) must also be called (pre-existing behaviour)."""
        session, orch = _make_mock_session(streaming=False)
        await _run_repl_one_turn(session)

        assert orch._status_cb_calls, "set_status_callback was never called"
        assert orch._status_cb_calls[-1] is None

    @pytest.mark.asyncio
    async def test_token_callback_cleared_even_when_handle_raises(self) -> None:
        """Finally block must clear callbacks even if orchestrator.handle() raises."""
        session, orch = _make_mock_session(streaming=False)
        orch.handle = AsyncMock(side_effect=RuntimeError("agent exploded"))

        # run_repl will catch the inner exception and continue to EOFError
        with patch("lidco.cli.app.Renderer"):
            await _run_repl_one_turn(session)

        # Even after the exception, the cleanup must have run
        assert orch._token_cb_calls[-1] is None, (
            "set_token_callback(None) not called after handle() raised"
        )

    @pytest.mark.asyncio
    async def test_token_callback_set_before_handle(self) -> None:
        """set_token_callback must be called with a non-None callback before handle()."""
        session, orch = _make_mock_session(streaming=False)

        handle_call_order: list[str] = []

        original_set_token = orch.set_token_callback.side_effect

        def track_set(cb: object) -> None:
            original_set_token(cb)
            if cb is not None:
                handle_call_order.append("set_callback")

        async def track_handle(*args, **kwargs):  # type: ignore[no-untyped-def]
            handle_call_order.append("handle")
            return _make_mock_response()

        orch.set_token_callback.side_effect = track_set
        orch.handle = track_handle

        await _run_repl_one_turn(session)

        # Callback must be registered before handle() is called
        assert handle_call_order == ["set_callback", "handle"], (
            f"Expected ['set_callback', 'handle'] but got {handle_call_order}"
        )
