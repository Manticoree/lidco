"""Background task execution with timeout and output capture."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from lidco.tasks.store import TaskStatus, TaskStore


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    success: bool
    output: str = ""
    error: str = ""
    duration_ms: float = 0.0


class TaskExecutor:
    """Execute tasks with timeout and concurrency control."""

    def __init__(self, store: TaskStore | None = None, max_concurrent: int = 4) -> None:
        self._store = store
        self._max_concurrent = max_concurrent
        self._running: dict[str, threading.Thread] = {}
        self._cancelled: set[str] = set()
        self._lock = threading.Lock()

    def execute_sync(
        self,
        task_id: str,
        callable_: Callable[..., Any],
        *args: Any,
        timeout: float = 0.0,
    ) -> ExecutionResult:
        """Run a task synchronously and return its result."""
        if self._store:
            self._store.update_status(task_id, TaskStatus.RUNNING)

        start = time.monotonic()
        result_holder: dict[str, Any] = {}

        def _run() -> None:
            try:
                out = callable_(*args)
                result_holder["output"] = str(out) if out is not None else ""
                result_holder["success"] = True
            except Exception as exc:
                result_holder["error"] = str(exc)
                result_holder["success"] = False

        thread = threading.Thread(target=_run, daemon=True)
        with self._lock:
            self._running[task_id] = thread
        thread.start()

        effective_timeout = timeout if timeout > 0 else None
        thread.join(timeout=effective_timeout)

        elapsed_ms = (time.monotonic() - start) * 1000

        with self._lock:
            self._running.pop(task_id, None)

        if thread.is_alive():
            # Timed out
            if self._store:
                self._store.update_status(task_id, TaskStatus.FAILED, error="timeout")
            return ExecutionResult(
                task_id=task_id,
                success=False,
                error="timeout",
                duration_ms=elapsed_ms,
            )

        success = result_holder.get("success", False)
        output = result_holder.get("output", "")
        error = result_holder.get("error", "")

        if self._store:
            status = TaskStatus.DONE if success else TaskStatus.FAILED
            self._store.update_status(task_id, status, output=output, error=error)

        return ExecutionResult(
            task_id=task_id,
            success=success,
            output=output,
            error=error,
            duration_ms=elapsed_ms,
        )

    def submit(
        self,
        task_id: str,
        callable_: Callable[..., Any],
        *args: Any,
        timeout: float = 0.0,
    ) -> None:
        """Queue a task for background execution."""

        def _background() -> None:
            self.execute_sync(task_id, callable_, *args, timeout=timeout)

        t = threading.Thread(target=_background, daemon=True)
        with self._lock:
            self._running[task_id] = t
        t.start()

    def cancel(self, task_id: str) -> bool:
        """Mark a task as cancelled. Returns True if it was running."""
        with self._lock:
            if task_id in self._running:
                self._cancelled.add(task_id)
                if self._store:
                    try:
                        self._store.update_status(task_id, TaskStatus.CANCELLED)
                    except Exception:
                        pass
                return True
        return False

    def is_running(self, task_id: str) -> bool:
        with self._lock:
            thread = self._running.get(task_id)
            if thread is None:
                return False
            return thread.is_alive()

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._running.values() if t.is_alive())
