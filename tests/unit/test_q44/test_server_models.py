"""Tests for server Pydantic models — Tasks 300–302."""

from __future__ import annotations

import pytest

from lidco.server.models import (
    ChatRequest,
    ChatResponse,
    CompleteRequest,
    CompleteResponse,
    ErrorResponse,
    ExplainRequest,
    ExplainResponse,
    MemoryAddRequest,
    MemoryDeleteRequest,
    MemoryListResponse,
    MemorySearchRequest,
    ReviewRequest,
    ReviewResponse,
    StatusResponse,
)


# ---------------------------------------------------------------------------
# ChatRequest
# ---------------------------------------------------------------------------

class TestChatRequest:
    def test_valid_minimal(self):
        req = ChatRequest(message="hello")
        assert req.message == "hello"
        assert req.agent is None
        assert req.context_files == []

    def test_with_agent(self):
        req = ChatRequest(message="hi", agent="reviewer")
        assert req.agent == "reviewer"

    def test_with_context_files(self):
        req = ChatRequest(message="hi", context_files=["src/main.py"])
        assert req.context_files == ["src/main.py"]

    def test_empty_message_fails(self):
        with pytest.raises(Exception):
            ChatRequest(message="")

    def test_message_too_long_fails(self):
        with pytest.raises(Exception):
            ChatRequest(message="x" * 100_001)


# ---------------------------------------------------------------------------
# ChatResponse
# ---------------------------------------------------------------------------

class TestChatResponse:
    def test_valid(self):
        resp = ChatResponse(content="done", agent="coder")
        assert resp.content == "done"
        assert resp.iterations == 0
        assert resp.tool_calls == []


# ---------------------------------------------------------------------------
# CompleteRequest
# ---------------------------------------------------------------------------

class TestCompleteRequest:
    def test_valid(self):
        req = CompleteRequest(
            file_path="src/main.py",
            content="def foo():\n    pass",
            cursor_line=1,
            cursor_column=0,
        )
        assert req.max_tokens == 256

    def test_negative_cursor_line_fails(self):
        with pytest.raises(Exception):
            CompleteRequest(
                file_path="f.py",
                content="x",
                cursor_line=-1,
                cursor_column=0,
            )

    def test_custom_max_tokens(self):
        req = CompleteRequest(
            file_path="f.py",
            content="x",
            cursor_line=0,
            cursor_column=0,
            max_tokens=512,
        )
        assert req.max_tokens == 512

    def test_max_tokens_too_large_fails(self):
        with pytest.raises(Exception):
            CompleteRequest(
                file_path="f.py",
                content="x",
                cursor_line=0,
                cursor_column=0,
                max_tokens=3000,
            )


# ---------------------------------------------------------------------------
# ReviewRequest
# ---------------------------------------------------------------------------

class TestReviewRequest:
    def test_minimal(self):
        req = ReviewRequest(code="print('hi')")
        assert req.file_path == ""
        assert req.language == ""

    def test_empty_code_fails(self):
        with pytest.raises(Exception):
            ReviewRequest(code="")


# ---------------------------------------------------------------------------
# ExplainRequest
# ---------------------------------------------------------------------------

class TestExplainRequest:
    def test_minimal(self):
        req = ExplainRequest(code="x = 1")
        assert req.language == ""

    def test_empty_code_fails(self):
        with pytest.raises(Exception):
            ExplainRequest(code="")


# ---------------------------------------------------------------------------
# MemoryAddRequest
# ---------------------------------------------------------------------------

class TestMemoryAddRequest:
    def test_valid(self):
        req = MemoryAddRequest(key="my-key", content="value")
        assert req.category == "general"
        assert req.tags == []

    def test_empty_key_fails(self):
        with pytest.raises(Exception):
            MemoryAddRequest(key="", content="x")

    def test_key_too_long_fails(self):
        with pytest.raises(Exception):
            MemoryAddRequest(key="x" * 201, content="x")


# ---------------------------------------------------------------------------
# MemorySearchRequest
# ---------------------------------------------------------------------------

class TestMemorySearchRequest:
    def test_valid(self):
        req = MemorySearchRequest(query="find something")
        assert req.limit == 20
        assert req.category is None

    def test_limit_bounds(self):
        with pytest.raises(Exception):
            MemorySearchRequest(query="x", limit=0)
        with pytest.raises(Exception):
            MemorySearchRequest(query="x", limit=101)


# ---------------------------------------------------------------------------
# StatusResponse
# ---------------------------------------------------------------------------

class TestStatusResponse:
    def test_valid(self):
        resp = StatusResponse(
            version="1.0.0",
            model="glm-4.7",
            agents=["coder", "reviewer"],
            memory_entries=5,
            project_dir="/tmp/proj",
        )
        assert resp.status == "running"
        assert len(resp.agents) == 2


# ---------------------------------------------------------------------------
# ErrorResponse
# ---------------------------------------------------------------------------

class TestErrorResponse:
    def test_valid(self):
        resp = ErrorResponse(error="Something failed")
        assert resp.detail == ""

    def test_with_detail(self):
        resp = ErrorResponse(error="Oops", detail="Line 42")
        assert "42" in resp.detail
