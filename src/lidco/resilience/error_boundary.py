"""ErrorBoundary — wrap calls so they never raise (stdlib only)."""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class BoundaryResult:
    """Outcome of a boundary-wrapped call."""

    success: bool
    value: Any
    error: Optional[Exception] = None
    error_type: Optional[str] = None
    traceback_str: Optional[str] = None


@dataclass
class _ErrorEntry:
    error: Exception
    error_type: str
    message: str
    timestamp: float


class ErrorBoundary:
    """Catch all exceptions so callers never see unhandled errors."""

    def __init__(self) -> None:
        self._log: list[_ErrorEntry] = []

    def catch(self, fn, *args, default=None, **kwargs) -> BoundaryResult:
        """Wrap a sync call — never raises."""
        try:
            result = fn(*args, **kwargs)
            return BoundaryResult(success=True, value=result)
        except Exception as exc:
            return self._handle_error(exc, default)

    async def async_catch(self, fn, *args, default=None, **kwargs) -> BoundaryResult:
        """Wrap an async call — never raises."""
        try:
            result = await fn(*args, **kwargs)
            return BoundaryResult(success=True, value=result)
        except Exception as exc:
            return self._handle_error(exc, default)

    def catch_with_handler(self, fn, handler_fn, *args, **kwargs) -> BoundaryResult:
        """Wrap a sync call with a custom error handler."""
        try:
            result = fn(*args, **kwargs)
            return BoundaryResult(success=True, value=result)
        except Exception as exc:
            self._record_error(exc)
            try:
                handled = handler_fn(exc)
            except Exception:
                handled = None
            return BoundaryResult(
                success=False,
                value=handled,
                error=exc,
                error_type=type(exc).__name__,
                traceback_str=traceback.format_exc(),
            )

    def _handle_error(self, exc: Exception, default: Any) -> BoundaryResult:
        self._record_error(exc)
        return BoundaryResult(
            success=False,
            value=default,
            error=exc,
            error_type=type(exc).__name__,
            traceback_str=traceback.format_exc(),
        )

    def _record_error(self, exc: Exception) -> None:
        self._log.append(_ErrorEntry(
            error=exc,
            error_type=type(exc).__name__,
            message=str(exc),
            timestamp=time.time(),
        ))

    @property
    def log(self) -> list[dict]:
        """Return list of all caught errors with timestamps."""
        return [
            {
                "error_type": e.error_type,
                "message": e.message,
                "timestamp": e.timestamp,
            }
            for e in self._log
        ]

    def clear_log(self) -> None:
        """Clear the error log."""
        self._log.clear()

    @property
    def error_count(self) -> int:
        """Return number of errors caught."""
        return len(self._log)
