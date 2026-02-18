"""FastAPI application — HTTP API for LIDCO IDE integration."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from lidco import __version__
from lidco.core.session import Session
from lidco.server.middleware import AuthTokenMiddleware, RequestLoggingMiddleware
from lidco.server.models import (
    AgentInfo,
    ChatRequest,
    ChatResponse,
    CompleteRequest,
    CompleteResponse,
    ContextResponse,
    ExplainRequest,
    ExplainResponse,
    MemoryAddRequest,
    MemoryEntryResponse,
    MemoryListResponse,
    MemorySearchRequest,
    ReviewRequest,
    ReviewResponse,
    StatusResponse,
)
from lidco.server.sse import stream_chat_response

logger = logging.getLogger(__name__)


def create_app(project_dir: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="LIDCO API",
        description="HTTP API for the LIDCO multi-agent coding assistant",
        version=__version__,
    )

    # ── Middleware ───────────────────────────────────────────────────────────

    allowed_origins = os.environ.get(
        "LIDCO_ALLOWED_ORIGINS",
        "http://localhost:*,http://127.0.0.1:*",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in allowed_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthTokenMiddleware)

    # ── Session (lazy singleton) ────────────────────────────────────────────

    _session_holder: dict[str, Session] = {}

    def _get_session() -> Session:
        if "session" not in _session_holder:
            _session_holder["session"] = Session(project_dir=project_dir)
        return _session_holder["session"]

    # ── Health ──────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ── Status ──────────────────────────────────────────────────────────────

    @app.get("/api/status", response_model=StatusResponse)
    async def status() -> StatusResponse:
        session = _get_session()
        return StatusResponse(
            version=__version__,
            model=session.config.llm.default_model,
            agents=session.agent_registry.list_names(),
            memory_entries=len(session.memory.list_all()),
            project_dir=str(session.project_dir),
        )

    # ── Agents ──────────────────────────────────────────────────────────────

    @app.get("/api/agents", response_model=list[AgentInfo])
    async def list_agents() -> list[AgentInfo]:
        session = _get_session()
        return [
            AgentInfo(name=a.name, description=a.description)
            for a in session.agent_registry.list_agents()
        ]

    # ── Chat ────────────────────────────────────────────────────────────────

    @app.post("/api/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest) -> ChatResponse:
        session = _get_session()
        context = session.get_full_context()

        # Append file contents to context if provided
        file_context = _build_file_context(req.context_files, session.project_dir)
        if file_context:
            context = f"{context}\n\n## Attached Files\n{file_context}"

        try:
            response = await session.orchestrator.handle(
                req.message,
                agent_name=req.agent,
                context=context,
            )
        except Exception as e:
            logger.exception("Chat error")
            raise HTTPException(status_code=500, detail=_error_detail(e)) from e

        return ChatResponse(
            content=response.content,
            agent=req.agent or "auto",
            model_used=response.model_used,
            iterations=response.iterations,
            tool_calls=response.tool_calls_made,
        )

    # ── Chat Stream (SSE) ──────────────────────────────────────────────────

    @app.post("/api/chat/stream")
    async def chat_stream(req: ChatRequest) -> EventSourceResponse:
        session = _get_session()

        async def event_generator():  # type: ignore[return]
            async for event in stream_chat_response(
                session, req.message, agent_name=req.agent
            ):
                yield event

        return EventSourceResponse(event_generator())

    # ── Complete (inline) ───────────────────────────────────────────────────

    @app.post("/api/complete", response_model=CompleteResponse)
    async def complete(req: CompleteRequest) -> CompleteResponse:
        session = _get_session()

        # Build a completion prompt from file context
        lines = req.content.splitlines()
        cursor_line = min(req.cursor_line, max(len(lines) - 1, 0))
        before = "\n".join(lines[: cursor_line + 1])
        after = "\n".join(lines[cursor_line + 1 :]) if cursor_line + 1 < len(lines) else ""

        prompt = (
            f"Complete the code at the cursor position. "
            f"Return ONLY the completion text, no explanation.\n\n"
            f"File: {req.file_path}\n"
            f"Language: {req.language}\n\n"
            f"Code before cursor:\n```\n{before[-2000:]}\n```\n\n"
            f"Code after cursor:\n```\n{after[:1000]}\n```"
        )

        try:
            from lidco.llm.base import Message

            response = await session.llm.complete(
                [
                    Message(role="system", content="You are a code completion assistant. Return ONLY the completion text."),
                    Message(role="user", content=prompt),
                ],
                max_tokens=req.max_tokens,
                temperature=0.0,
                role="completion",
            )
        except Exception as e:
            logger.exception("Completion error")
            raise HTTPException(status_code=500, detail=_error_detail(e)) from e

        return CompleteResponse(
            completion=response.content.strip(),
            model_used=response.model,
        )

    # ── Review ──────────────────────────────────────────────────────────────

    @app.post("/api/review", response_model=ReviewResponse)
    async def review(req: ReviewRequest) -> ReviewResponse:
        session = _get_session()

        message = f"Review the following code"
        if req.file_path:
            message += f" from `{req.file_path}`"
        if req.language:
            message += f" ({req.language})"
        if req.instructions:
            message += f". {req.instructions}"
        message += f":\n\n```{req.language}\n{req.code}\n```"

        try:
            response = await session.orchestrator.handle(
                message, agent_name="reviewer", context=session.get_full_context()
            )
        except Exception as e:
            logger.exception("Review error")
            raise HTTPException(status_code=500, detail=_error_detail(e)) from e

        return ReviewResponse(
            review=response.content,
            agent="reviewer",
            model_used=response.model_used,
        )

    # ── Explain ─────────────────────────────────────────────────────────────

    @app.post("/api/explain", response_model=ExplainResponse)
    async def explain(req: ExplainRequest) -> ExplainResponse:
        session = _get_session()

        message = f"Explain the following code"
        if req.file_path:
            message += f" from `{req.file_path}`"
        if req.language:
            message += f" ({req.language})"
        message += f":\n\n```{req.language}\n{req.code}\n```"

        try:
            response = await session.orchestrator.handle(
                message, agent_name="coder", context=session.get_full_context()
            )
        except Exception as e:
            logger.exception("Explain error")
            raise HTTPException(status_code=500, detail=_error_detail(e)) from e

        return ExplainResponse(
            explanation=response.content,
            model_used=response.model_used,
        )

    # ── Memory ──────────────────────────────────────────────────────────────

    @app.get("/api/memory", response_model=MemoryListResponse)
    async def memory_list() -> MemoryListResponse:
        session = _get_session()
        entries = session.memory.list_all()
        return MemoryListResponse(
            entries=[
                MemoryEntryResponse(
                    key=e.key,
                    content=e.content,
                    category=e.category,
                    tags=list(e.tags),
                    created_at=e.created_at,
                    source=e.source,
                )
                for e in entries
            ],
            total=len(entries),
        )

    @app.post("/api/memory", response_model=MemoryEntryResponse)
    async def memory_add(req: MemoryAddRequest) -> MemoryEntryResponse:
        session = _get_session()
        entry = session.memory.add(
            key=req.key,
            content=req.content,
            category=req.category,
            tags=req.tags,
        )
        return MemoryEntryResponse(
            key=entry.key,
            content=entry.content,
            category=entry.category,
            tags=list(entry.tags),
            created_at=entry.created_at,
            source=entry.source,
        )

    @app.post("/api/memory/search", response_model=MemoryListResponse)
    async def memory_search(req: MemorySearchRequest) -> MemoryListResponse:
        session = _get_session()
        results = session.memory.search(
            req.query, category=req.category, limit=req.limit
        )
        return MemoryListResponse(
            entries=[
                MemoryEntryResponse(
                    key=e.key,
                    content=e.content,
                    category=e.category,
                    tags=list(e.tags),
                    created_at=e.created_at,
                    source=e.source,
                )
                for e in results
            ],
            total=len(results),
        )

    @app.delete("/api/memory/{key}")
    async def memory_delete(key: str) -> dict[str, bool]:
        session = _get_session()
        removed = session.memory.remove(key)
        if not removed:
            raise HTTPException(status_code=404, detail=f"Memory key '{key}' not found")
        return {"deleted": True}

    # ── Context ─────────────────────────────────────────────────────────────

    @app.get("/api/context", response_model=ContextResponse)
    async def get_context() -> ContextResponse:
        session = _get_session()
        return ContextResponse(
            context=session.get_full_context(),
            project_dir=str(session.project_dir),
        )

    return app


_DEBUG = os.environ.get("LIDCO_DEBUG", "").lower() in ("1", "true")


def _error_detail(exc: Exception) -> str:
    """Return error detail — verbose in debug mode, sanitized in production."""
    if _DEBUG:
        return str(exc)
    return "An internal error occurred. Set LIDCO_DEBUG=1 for details."


def _build_file_context(file_paths: list[str], project_dir: Path) -> str:
    """Read file contents for context injection.

    Only allows files within the project directory to prevent path traversal.
    """
    project_root = project_dir.resolve()
    parts: list[str] = []
    for fp in file_paths:
        try:
            p = Path(fp).resolve()
            if not p.is_relative_to(project_root):
                parts.append(f"### {fp}\n(access denied — outside project)")
                continue
            if p.is_file() and p.stat().st_size < 500_000:
                content = p.read_text(encoding="utf-8", errors="replace")
                parts.append(f"### {fp}\n```\n{content}\n```")
        except (OSError, ValueError):
            parts.append(f"### {fp}\n(could not read)")
    return "\n\n".join(parts)


def run_server(
    host: str = "127.0.0.1",
    port: int = 8321,
    project_dir: Path | None = None,
) -> None:
    """Start the LIDCO HTTP server."""
    import uvicorn

    app = create_app(project_dir=project_dir)
    logger.info("Starting LIDCO server on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
