"""AsyncConsolidationScheduler — schedule periodic memory consolidation.

Task 732: Q120.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ConsolidationJob:
    status: str  # "idle" | "running" | "completed" | "failed"
    last_run: Optional[float] = None
    last_report: Any = None
    run_count: int = 0
    error: str = ""


class AsyncConsolidationScheduler:
    """Run a MemoryConsolidator periodically in a background daemon thread."""

    def __init__(self, consolidator=None, event_bus=None) -> None:
        self._consolidator = consolidator
        self._event_bus = event_bus
        self._job = ConsolidationJob(status="idle")
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def run_once(self, store=None) -> ConsolidationJob:
        """Run consolidation once synchronously and return updated job."""
        if self._consolidator is None:
            with self._lock:
                self._job = ConsolidationJob(
                    status="failed",
                    last_run=time.time(),
                    run_count=self._job.run_count + 1,
                    error="No consolidator configured",
                )
            return self._job

        try:
            report = self._consolidator.consolidate(store=store)
            with self._lock:
                self._job = ConsolidationJob(
                    status="completed",
                    last_run=time.time(),
                    last_report=report,
                    run_count=self._job.run_count + 1,
                    error="",
                )
            if self._event_bus is not None:
                self._event_bus.publish({"type": "consolidation_complete", "report": report})
        except Exception as exc:
            with self._lock:
                self._job = ConsolidationJob(
                    status="failed",
                    last_run=time.time(),
                    run_count=self._job.run_count + 1,
                    error=str(exc),
                )

        return self._job

    def get_job(self) -> ConsolidationJob:
        with self._lock:
            return self._job

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def schedule(self, interval_s: float = 300.0, store=None) -> None:
        """Start (or replace) a background thread that runs every *interval_s* seconds."""
        self.cancel()
        self._stop_event.clear()

        def _loop() -> None:
            while not self._stop_event.wait(timeout=interval_s):
                self.run_once(store=store)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        """Stop the background thread if running."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None
