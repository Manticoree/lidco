"""Tests for LLMBatcher — Q63 Task 428."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestBatchRequest:
    def test_fields(self):
        from lidco.ai.batch_llm import BatchRequest
        req = BatchRequest(id="r1", messages=[{"role": "user", "content": "hi"}], model="gpt-4o")
        assert req.id == "r1"
        assert req.model == "gpt-4o"
        assert req.callback is None


class TestLLMBatcher:
    def test_add_increments_queue(self):
        from lidco.ai.batch_llm import LLMBatcher, BatchRequest
        batcher = LLMBatcher(max_concurrent=3)
        req = BatchRequest(id="r1", messages=[])
        batcher.add(req)
        assert batcher.queue_size() == 1

    def test_add_returns_true_at_auto_flush_threshold(self):
        from lidco.ai.batch_llm import LLMBatcher, BatchRequest
        batcher = LLMBatcher(auto_flush_after=2)
        req1 = BatchRequest(id="r1", messages=[])
        req2 = BatchRequest(id="r2", messages=[])
        batcher.add(req1)
        result = batcher.add(req2)
        assert result is True

    def test_clear_empties_queue(self):
        from lidco.ai.batch_llm import LLMBatcher, BatchRequest
        batcher = LLMBatcher()
        batcher.add(BatchRequest(id="r1", messages=[]))
        batcher.clear()
        assert batcher.queue_size() == 0

    @pytest.mark.asyncio
    async def test_flush_empty_returns_empty_dict(self):
        from lidco.ai.batch_llm import LLMBatcher
        batcher = LLMBatcher()
        result = await batcher.flush()
        assert result == {}

    @pytest.mark.asyncio
    async def test_flush_with_llm(self):
        from lidco.ai.batch_llm import LLMBatcher, BatchRequest
        batcher = LLMBatcher(max_concurrent=2)
        mock_resp = MagicMock()
        mock_resp.content = "response_r1"
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_resp)
        batcher.add(BatchRequest(id="r1", messages=[{"role": "user", "content": "q1"}]))
        result = await batcher.flush(llm=mock_llm)
        assert "r1" in result
        assert "response_r1" in result["r1"]

    @pytest.mark.asyncio
    async def test_flush_handles_no_provider(self):
        from lidco.ai.batch_llm import LLMBatcher, BatchRequest
        batcher = LLMBatcher()
        batcher.add(BatchRequest(id="r1", messages=[]))
        result = await batcher.flush()  # No LLM set
        assert "r1" in result
        assert "[ERROR]" in result["r1"]

    @pytest.mark.asyncio
    async def test_flush_multiple_requests(self):
        from lidco.ai.batch_llm import LLMBatcher, BatchRequest
        batcher = LLMBatcher(max_concurrent=3)
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=lambda **kw: MagicMock(content="ok"))
        for i in range(5):
            batcher.add(BatchRequest(id=str(i), messages=[]))
        result = await batcher.flush(llm=mock_llm)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_callback_called(self):
        from lidco.ai.batch_llm import LLMBatcher, BatchRequest
        called_with = []
        def cb(text):
            called_with.append(text)
        mock_resp = MagicMock()
        mock_resp.content = "hello"
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_resp)
        batcher = LLMBatcher()
        batcher.add(BatchRequest(id="r1", messages=[], callback=cb))
        await batcher.flush(llm=mock_llm)
        assert called_with == ["hello"]

    def test_set_llm(self):
        from lidco.ai.batch_llm import LLMBatcher
        batcher = LLMBatcher()
        mock_llm = MagicMock()
        batcher.set_llm(mock_llm)
        assert batcher._llm is mock_llm
