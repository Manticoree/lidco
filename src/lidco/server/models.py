"""Pydantic request/response models for the LIDCO API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Request models ──────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request body for /api/chat and /api/chat/stream."""

    message: str = Field(..., min_length=1, max_length=100_000)
    agent: str | None = None
    context_files: list[str] = Field(default_factory=list)


class CompleteRequest(BaseModel):
    """Request body for /api/complete (inline code completion)."""

    file_path: str
    content: str
    cursor_line: int = Field(..., ge=0)
    cursor_column: int = Field(..., ge=0)
    language: str = ""
    max_tokens: int = Field(default=256, ge=1, le=2048)


class ReviewRequest(BaseModel):
    """Request body for /api/review."""

    code: str = Field(..., min_length=1)
    file_path: str = ""
    language: str = ""
    instructions: str = ""


class ExplainRequest(BaseModel):
    """Request body for /api/explain."""

    code: str = Field(..., min_length=1)
    file_path: str = ""
    language: str = ""


class MemoryAddRequest(BaseModel):
    """Request body for adding a memory entry."""

    key: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    category: str = "general"
    tags: list[str] = Field(default_factory=list)


class MemorySearchRequest(BaseModel):
    """Request body for searching memories."""

    query: str = Field(..., min_length=1)
    category: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class MemoryDeleteRequest(BaseModel):
    """Request body for deleting a memory entry."""

    key: str = Field(..., min_length=1)


# ── Response models ─────────────────────────────────────────────────────────


class AgentInfo(BaseModel):
    """Info about a single agent."""

    name: str
    description: str


class ChatResponse(BaseModel):
    """Response body for /api/chat."""

    content: str
    agent: str
    model_used: str = ""
    iterations: int = 0
    tool_calls: list[dict] = Field(default_factory=list)


class CompleteResponse(BaseModel):
    """Response body for /api/complete."""

    completion: str
    model_used: str = ""


class ReviewResponse(BaseModel):
    """Response body for /api/review."""

    review: str
    agent: str = "reviewer"
    model_used: str = ""


class ExplainResponse(BaseModel):
    """Response body for /api/explain."""

    explanation: str
    agent: str = "coder"
    model_used: str = ""


class MemoryEntryResponse(BaseModel):
    """A single memory entry in responses."""

    key: str
    content: str
    category: str
    tags: list[str] = Field(default_factory=list)
    created_at: str = ""
    source: str = ""


class MemoryListResponse(BaseModel):
    """Response for memory list/search."""

    entries: list[MemoryEntryResponse]
    total: int


class StatusResponse(BaseModel):
    """Response body for /api/status."""

    version: str
    status: str = "running"
    model: str
    agents: list[str]
    memory_entries: int
    project_dir: str


class ContextResponse(BaseModel):
    """Response body for /api/context."""

    context: str
    project_dir: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str = ""
