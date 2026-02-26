"""Tests for ContextRetriever query expansion behaviour.

Covers the fix for the fire-and-forget LLM task that was created when
_retrieve_expanded() was called from within a running event loop:

  Before the fix:
    loop.create_task(_run_and_store())   # task set future nobody reads
    # fall back to single query          # LLM API call wasted

  After the fix:
    # just skip expansion and fall back to single query — no wasted call
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lidco.rag.retriever import ContextRetriever


def _make_retriever(*, with_llm: bool = True) -> tuple[ContextRetriever, MagicMock, MagicMock]:
    """Return (retriever, store_mock, llm_mock)."""
    store = MagicMock()
    store.search_hybrid.return_value = []
    indexer = MagicMock()
    llm = MagicMock()
    llm.complete = AsyncMock(return_value=MagicMock(content="alt1\nalt2\nalt3"))
    return (
        ContextRetriever(
            store=store,
            indexer=indexer,
            project_dir=Path("/tmp/test"),
            llm=llm if with_llm else None,
        ),
        store,
        llm,
    )


class TestQueryExpansionRunningLoop:
    @pytest.mark.asyncio
    async def test_expansion_skipped_inside_running_loop(self) -> None:
        """When called from within a running event loop, expansion must be skipped.

        The event loop IS running during a pytest.mark.asyncio test, so this
        exercises exactly the code path that previously created the dead task.
        """
        retriever, store, llm = _make_retriever()

        # retrieve() is synchronous; it internally calls _retrieve_expanded()
        # which detects the running loop and skips expansion.
        retriever.retrieve("find authentication patterns", query_expansion=True)

        # LLM must NOT have been called — no wasted API call
        llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_query_used_when_expansion_skipped(self) -> None:
        """Only one search (the original query) is performed when expansion is skipped."""
        retriever, store, _ = _make_retriever()

        retriever.retrieve("error handling", query_expansion=True)

        # Exactly one search with the original query
        assert store.search_hybrid.call_count == 1
        call_kwargs = store.search_hybrid.call_args
        assert call_kwargs.kwargs.get("query") == "error handling" or (
            call_kwargs.args and call_kwargs.args[0] == "error handling"
            or (call_kwargs.kwargs and call_kwargs.kwargs.get("query") == "error handling")
        )

    @pytest.mark.asyncio
    async def test_no_create_task_called_inside_running_loop(self) -> None:
        """loop.create_task must NOT be called — the dead task was removed."""
        import asyncio

        retriever, store, _ = _make_retriever()
        loop = asyncio.get_event_loop()

        with patch.object(loop, "create_task") as mock_create_task:
            retriever.retrieve("some query", query_expansion=True)

        mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_expansion_disabled_does_not_call_llm(self) -> None:
        """With query_expansion=False, LLM is never consulted."""
        retriever, store, llm = _make_retriever()

        retriever.retrieve("test query", query_expansion=False)

        llm.complete.assert_not_called()
        assert store.search_hybrid.call_count == 1

    @pytest.mark.asyncio
    async def test_no_llm_falls_back_gracefully(self) -> None:
        """If no LLM is configured, retrieve() works with a single query."""
        retriever, store, _ = _make_retriever(with_llm=False)

        result = retriever.retrieve("some query", query_expansion=True)

        assert store.search_hybrid.call_count == 1
        assert isinstance(result, str)

    def test_expansion_runs_in_non_async_context(self) -> None:
        """When there is no running loop, expansion goes through the normal path."""
        retriever, store, llm = _make_retriever()

        # Simulate a non-async context: patch get_event_loop to raise RuntimeError
        # so the code hits the `except RuntimeError: asyncio.run(_expand())` branch.
        # Use a side_effect that closes the coroutine to avoid RuntimeWarning.
        def _fake_run(coro):  # type: ignore[no-untyped-def]
            coro.close()  # prevent "coroutine never awaited" warning
            return ["alt query 1", "alt query 2"]

        with patch("asyncio.get_event_loop", side_effect=RuntimeError("no loop")):
            with patch("asyncio.run", side_effect=_fake_run):
                retriever.retrieve("original query", query_expansion=True)

        # With two extra queries, store.search_hybrid should be called 3 times
        assert store.search_hybrid.call_count == 3
