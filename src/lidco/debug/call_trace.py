"""Q133: Function call tracer."""
from __future__ import annotations

import functools
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class TraceEntry:
    fn_name: str
    args: tuple
    kwargs: dict
    result: Any
    error: str = ""
    elapsed: float = 0.0
    timestamp: float = 0.0


class CallTracer:
    """Decorator-based function call tracer."""

    def __init__(self) -> None:
        self._entries: list[TraceEntry] = []

    def trace(self, fn: Callable) -> Callable:
        """Wrap *fn* and record a TraceEntry on each call."""

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            ts = time.time()
            error = ""
            result = None
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                error = str(exc)
                raise
            finally:
                elapsed = time.monotonic() - start
                self._entries.append(
                    TraceEntry(
                        fn_name=fn.__name__,
                        args=args,
                        kwargs=dict(kwargs),
                        result=result,
                        error=error,
                        elapsed=elapsed,
                        timestamp=ts,
                    )
                )
            return result

        return wrapper

    def entries(self) -> list[TraceEntry]:
        return list(self._entries)

    def last(self, fn_name: str | None = None) -> Optional[TraceEntry]:
        if not self._entries:
            return None
        if fn_name is None:
            return self._entries[-1]
        for entry in reversed(self._entries):
            if entry.fn_name == fn_name:
                return entry
        return None

    def clear(self) -> None:
        self._entries.clear()

    def summary(self) -> dict:
        """Return {fn_name: {"calls": N, "errors": N, "avg_elapsed": float}}."""
        agg: dict[str, dict] = {}
        for e in self._entries:
            if e.fn_name not in agg:
                agg[e.fn_name] = {"calls": 0, "errors": 0, "_total_elapsed": 0.0}
            agg[e.fn_name]["calls"] += 1
            if e.error:
                agg[e.fn_name]["errors"] += 1
            agg[e.fn_name]["_total_elapsed"] += e.elapsed

        result: dict = {}
        for name, data in agg.items():
            calls = data["calls"]
            result[name] = {
                "calls": calls,
                "errors": data["errors"],
                "avg_elapsed": data["_total_elapsed"] / calls if calls else 0.0,
            }
        return result
