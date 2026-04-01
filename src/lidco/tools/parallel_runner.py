"""Execute independent tools concurrently."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import Enum


class ToolCallStatus(str, Enum):
    """Status of a tool call."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class ToolCall:
    """A single tool invocation record."""

    id: str
    tool_name: str
    args: str = ""
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: str = ""
    duration: float = 0.0
    error: str = ""


@dataclass(frozen=True)
class ParallelResult:
    """Aggregated result of parallel tool execution."""

    calls: tuple[ToolCall, ...] = ()
    total_duration: float = 0.0
    completed: int = 0
    failed: int = 0


class ParallelToolRunner:
    """Manages parallel tool call scheduling and tracking."""

    def __init__(self, max_concurrent: int = 5, timeout: float = 30.0) -> None:
        self._max_concurrent = max_concurrent
        self._timeout = timeout
        self._queue: list[ToolCall] = []

    def add_call(self, tool_name: str, args: str = "") -> ToolCall:
        """Create a tool call and add it to the queue."""
        call = ToolCall(
            id=uuid.uuid4().hex[:12],
            tool_name=tool_name,
            args=args,
        )
        self._queue.append(call)
        return call

    def detect_dependencies(self, calls: list[ToolCall]) -> list[list[ToolCall]]:
        """Group calls into independent batches.

        Simple heuristic: same tool name => sequential, different => parallel.
        """
        batches: list[list[ToolCall]] = []
        seen_tools: dict[str, int] = {}
        for call in calls:
            if call.tool_name in seen_tools:
                batch_idx = seen_tools[call.tool_name]
                # Place in next batch after the last one containing this tool
                target = batch_idx + 1
                if target >= len(batches):
                    batches.append([])
                batches[target].append(call)
                seen_tools[call.tool_name] = target
            else:
                if not batches:
                    batches.append([])
                batches[0].append(call)
                seen_tools[call.tool_name] = 0
        return batches

    def simulate_run(self, calls: list[ToolCall]) -> ParallelResult:
        """Simulate execution by marking all calls as completed."""
        start = time.monotonic()
        completed_calls: list[ToolCall] = []
        for call in calls:
            completed_calls.append(ToolCall(
                id=call.id,
                tool_name=call.tool_name,
                args=call.args,
                status=ToolCallStatus.COMPLETED,
                result=f"Simulated result for {call.tool_name}",
                duration=0.0,
                error="",
            ))
        elapsed = time.monotonic() - start
        return ParallelResult(
            calls=tuple(completed_calls),
            total_duration=elapsed,
            completed=len(completed_calls),
            failed=0,
        )

    def mark_completed(self, call_id: str, result: str, duration: float = 0.0) -> ToolCall:
        """Return a new ToolCall marked as completed."""
        original = self._find_call(call_id)
        return ToolCall(
            id=original.id,
            tool_name=original.tool_name,
            args=original.args,
            status=ToolCallStatus.COMPLETED,
            result=result,
            duration=duration,
        )

    def mark_failed(self, call_id: str, error: str) -> ToolCall:
        """Return a new ToolCall marked as failed."""
        original = self._find_call(call_id)
        return ToolCall(
            id=original.id,
            tool_name=original.tool_name,
            args=original.args,
            status=ToolCallStatus.FAILED,
            error=error,
        )

    def get_pending(self) -> list[ToolCall]:
        """Return all pending calls in the queue."""
        return [c for c in self._queue if c.status == ToolCallStatus.PENDING]

    def summary(self, result: ParallelResult) -> str:
        """One-line summary of a parallel run."""
        return (
            f"Parallel run: {result.completed} completed, {result.failed} failed, "
            f"{len(result.calls)} total in {result.total_duration:.3f}s"
        )

    def _find_call(self, call_id: str) -> ToolCall:
        """Find a call in the queue by id."""
        for call in self._queue:
            if call.id == call_id:
                return call
        raise KeyError(f"No call with id '{call_id}' in queue.")
