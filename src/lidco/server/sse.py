"""SSE (Server-Sent Events) streaming for chat responses."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any

from lidco.core.session import Session

logger = logging.getLogger(__name__)

# Sentinel object to signal the orchestrator has finished.
_DONE = object()


async def stream_chat_response(
    session: Session,
    message: str,
    agent_name: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a chat response as SSE events.

    Event types:
      - start: chat started
      - status: processing stage update with elapsed time
      - token: a chunk of the response text (real-time)
      - tool_start: a tool call is about to execute
      - tool_end: a tool call finished (success or error)
      - tool_call: legacy per-tool summary (kept for backwards compat)
      - done: final metadata (model, iterations, agent)
      - error: something went wrong

    Tokens, tool events, and status updates are all streamed in real-time
    via an asyncio queue bridging sync callbacks with the async generator.
    """
    start_time = time.monotonic()
    queue: asyncio.Queue[dict[str, Any] | object] = asyncio.Queue()

    def _elapsed() -> float:
        return round(time.monotonic() - start_time, 1)

    # ── Callbacks (sync, called from agent loop) ─────────────────────────

    def on_status(status: str) -> None:
        try:
            queue.put_nowait({"_type": "status", "status": status, "elapsed": _elapsed()})
        except asyncio.QueueFull:
            pass

    def on_stream_text(text: str) -> None:
        if text:
            try:
                queue.put_nowait({"_type": "token", "text": text})
            except asyncio.QueueFull:
                pass

    def on_tool_event(
        event: str, tool_name: str, args: dict, result: Any = None,
    ) -> None:
        try:
            if event == "start":
                queue.put_nowait({
                    "_type": "tool_start",
                    "tool": tool_name,
                    "args": _safe_args(args),
                })
            elif event == "end":
                success = getattr(result, "success", True) if result is not None else True
                output = getattr(result, "output", "") if result is not None else ""
                error = getattr(result, "error", "") if result is not None else ""
                queue.put_nowait({
                    "_type": "tool_end",
                    "tool": tool_name,
                    "success": success,
                    "output": _truncate(output, 200),
                    "error": _truncate(error, 200),
                })
        except asyncio.QueueFull:
            pass

    # ── Run orchestrator as background task ──────────────────────────────

    async def run_orchestrator() -> Any:
        try:
            context = session.get_full_context()
            orch = session.orchestrator
            orch.set_status_callback(on_status)
            orch.set_stream_callback(on_stream_text)
            orch.set_tool_event_callback(on_tool_event)
            result = await orch.handle(
                message,
                agent_name=agent_name,
                context=context,
            )
            orch.set_status_callback(None)
            orch.set_stream_callback(None)
            orch.set_tool_event_callback(None)
            return result
        finally:
            queue.put_nowait(_DONE)

    # ── SSE generator ────────────────────────────────────────────────────

    try:
        yield _sse_event("start", {"agent": agent_name or "auto"})

        task = asyncio.create_task(run_orchestrator())

        # Stream events in real-time as they arrive (5 min timeout)
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=300.0)
            except asyncio.TimeoutError:
                logger.error("SSE stream timeout — orchestrator may have hung")
                yield _sse_event("error", {"message": "Stream timeout"})
                task.cancel()
                return
            if item is _DONE:
                break
            if isinstance(item, dict):
                event_type = item.pop("_type", "status")
                yield _sse_event(event_type, item)

        response = await task

        # Legacy tool_call events for backwards compat (clients that
        # don't understand tool_start/tool_end still get a summary)
        for tc in response.tool_calls_made:
            yield _sse_event("tool_call", tc)

        # If content was NOT streamed via tokens (e.g. streaming disabled
        # on the LLM side), send it now in chunks
        if not response.content:
            pass  # nothing to send
        # Content was already streamed via on_stream_text tokens — skip
        # re-sending to avoid duplication.

        # Done event with metadata
        total_time = round(time.monotonic() - start_time, 1)
        tokens = response.token_usage
        yield _sse_event(
            "done",
            {
                "agent": agent_name or "auto",
                "model_used": response.model_used,
                "iterations": response.iterations,
                "tool_calls_count": len(response.tool_calls_made),
                "total_tokens": tokens.total_tokens,
                "elapsed": total_time,
            },
        )

    except Exception as e:
        logger.exception("SSE stream error")
        yield _sse_event("error", {"message": str(e)})
        return


def _sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _safe_args(args: dict) -> dict:
    """Serialize args, truncating large values for the SSE payload."""
    result = {}
    for k, v in args.items():
        s = str(v)
        result[k] = s[:200] + "..." if len(s) > 200 else s
    return result


def _truncate(text: str, max_len: int) -> str:
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text
