"""Batched parallel LLM calls — Task 428.

Queues multiple LLM requests and executes them concurrently using
``asyncio.gather``, bounded by a configurable concurrency limit.

Usage::

    batcher = LLMBatcher(max_concurrent=5)
    batcher.add(BatchRequest(id="r1", messages=[...], model="gpt-4o"))
    batcher.add(BatchRequest(id="r2", messages=[...], model="gpt-4o"))
    results = await batcher.flush()  # {"r1": "response1", "r2": "response2"}
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

from lidco.core.config import PermissionLevel
from lidco.tools.base import BaseTool

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class BatchRequest:
    """A single LLM request queued for batch execution.

    Attributes:
        id: Unique identifier for this request.
        messages: Conversation messages.
        model: Model identifier string.
        max_tokens: Maximum tokens for the response.
        callback: Optional async callback fired with the response string.
    """

    id: str
    messages: list[dict[str, Any]]
    model: str = ""
    max_tokens: int = 1024
    callback: Callable[[str], Any] | None = None


@dataclass
class _BatchSlot:
    """Internal slot pairing a request with its LLM callable."""

    request: BatchRequest
    llm_fn: Callable[..., Any] | None = None


class LLMBatcher:
    """Collects LLM requests and runs them in parallel.

    Args:
        max_concurrent: Maximum number of simultaneous LLM calls.
        auto_flush_after: Automatically flush when queue reaches this size.
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        auto_flush_after: int = 10,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.auto_flush_after = auto_flush_after
        self._queue: list[BatchRequest] = []
        self._llm: Any = None  # BaseLLMProvider, set externally
        self._semaphore: asyncio.Semaphore | None = None

    def set_llm(self, llm: Any) -> None:
        """Bind an LLM provider for executing requests."""
        self._llm = llm

    def add(self, request: BatchRequest) -> bool:
        """Add a request to the queue.

        Returns:
            True if auto-flush threshold was reached (caller may want to flush).
        """
        self._queue.append(request)
        return len(self._queue) >= self.auto_flush_after

    def queue_size(self) -> int:
        """Return the number of requests currently in the queue."""
        return len(self._queue)

    def clear(self) -> None:
        """Discard all pending requests without executing them."""
        self._queue.clear()

    async def flush(
        self,
        llm: Any = None,
    ) -> dict[str, str]:
        """Execute all queued requests concurrently.

        Args:
            llm: Optional LLM provider override.

        Returns:
            Dict mapping request id → response string.
        """
        if not self._queue:
            return {}

        provider = llm or self._llm
        pending = list(self._queue)
        self._queue.clear()

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def _run_one(req: BatchRequest) -> tuple[str, str]:
            async with semaphore:
                try:
                    if provider is None:
                        raise RuntimeError("No LLM provider configured")
                    params: dict[str, Any] = {
                        "messages": req.messages,
                        "max_tokens": req.max_tokens,
                    }
                    if req.model:
                        params["model"] = req.model

                    resp = await provider.complete(**params)
                    content = ""
                    if resp:
                        content = getattr(resp, "content", "") or str(resp)

                    if req.callback is not None:
                        try:
                            result = req.callback(content)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as cb_exc:
                            logger.debug("Batch callback error for %s: %s", req.id, cb_exc)

                    return req.id, content
                except Exception as exc:
                    logger.debug("Batch request %s failed: %s", req.id, exc)
                    return req.id, f"[ERROR] {exc}"

        tasks = [_run_one(r) for r in pending]
        pairs = await asyncio.gather(*tasks, return_exceptions=True)

        results: dict[str, str] = {}
        for i, pair in enumerate(pairs):
            if isinstance(pair, Exception):
                results[pending[i].id] = f"[ERROR] {pair}"
            else:
                req_id, content = pair
                results[req_id] = content

        return results


# ---------------------------------------------------------------------------
# BatchLLMTool
# ---------------------------------------------------------------------------

class BatchLLMTool(BaseTool):
    """Tool that runs multiple prompts in a single batched LLM call.

    Permission: AUTO
    """

    name: str = "batch_llm"
    description: str = (
        "Run multiple prompts concurrently via batched LLM calls. "
        "Takes a list of prompt strings and returns all responses."
    )
    permission: PermissionLevel = PermissionLevel.AUTO

    def __init__(self, llm: Any = None) -> None:
        super().__init__()
        self._batcher = LLMBatcher()
        if llm is not None:
            self._batcher.set_llm(llm)

    def set_llm(self, llm: Any) -> None:
        self._batcher.set_llm(llm)

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of prompts to run in parallel.",
                },
                "model": {
                    "type": "string",
                    "description": "Model to use for all prompts (optional).",
                    "default": "",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Max tokens per response.",
                    "default": 512,
                },
            },
            "required": ["prompts"],
        }

    async def execute(self, **kwargs: Any) -> str:
        prompts: list[str] = kwargs.get("prompts", [])
        model: str = kwargs.get("model", "")
        max_tokens: int = int(kwargs.get("max_tokens", 512))

        if not prompts:
            return "No prompts provided."

        for i, p in enumerate(prompts):
            req = BatchRequest(
                id=str(i),
                messages=[{"role": "user", "content": p}],
                model=model,
                max_tokens=max_tokens,
            )
            self._batcher.add(req)

        results = await self._batcher.flush()

        lines = []
        for i in range(len(prompts)):
            resp = results.get(str(i), "[no response]")
            lines.append(f"**Prompt {i + 1}:** {prompts[i][:60]}{'…' if len(prompts[i]) > 60 else ''}")
            lines.append(f"**Response:** {resp}")
            lines.append("")

        return "\n".join(lines).rstrip()
