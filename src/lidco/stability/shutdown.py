"""
Shutdown Orchestrator.

Registers and executes shutdown handlers in priority order, saves session
state to disk, and reports execution results.
"""
from __future__ import annotations

import json
import os
import time


class ShutdownOrchestrator:
    """Coordinate graceful application shutdown."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._handlers: list[dict] = []  # {"name", "handler", "priority"}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_handler(
        self, name: str, handler: callable, priority: int = 0
    ) -> None:
        """Register a shutdown handler.

        Args:
            name: Unique human-readable name for the handler.
            handler: Zero-argument callable to invoke during shutdown.
            priority: Higher values run first (default 0).
        """
        self._handlers.append(
            {"name": name, "handler": handler, "priority": priority}
        )

    def execute_shutdown(self) -> dict:
        """Execute all registered handlers in priority order (highest first).

        Each handler is called with no arguments. Handlers that raise are
        recorded as failures but do not prevent subsequent handlers from
        running.

        Returns:
            dict with keys:
                "success" (bool): True if every handler completed without error
                "executed" (list[str]): names of handlers that ran successfully
                "failed" (list[dict]): each dict has "name" (str) and "error" (str)
                "total_time_ms" (float): wall-clock time for the whole shutdown
        """
        ordered = sorted(
            self._handlers, key=lambda h: h["priority"], reverse=True
        )
        executed: list[str] = []
        failed: list[dict] = []
        start = time.perf_counter()

        for entry in ordered:
            try:
                entry["handler"]()
                executed.append(entry["name"])
            except Exception as exc:
                failed.append({"name": entry["name"], "error": str(exc)})

        total_ms = (time.perf_counter() - start) * 1000.0
        return {
            "success": len(failed) == 0,
            "executed": executed,
            "failed": failed,
            "total_time_ms": total_ms,
        }

    def save_state(self, state: dict, path: str) -> dict:
        """Persist *state* as JSON to *path*.

        Args:
            state: Arbitrary JSON-serialisable dict.
            path: File path to write.

        Returns:
            dict with keys:
                "saved" (bool): True if write succeeded
                "path" (str): resolved file path
                "size_bytes" (int): bytes written (0 on failure)
        """
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            payload = json.dumps(state, indent=2, default=str)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(payload)
            return {
                "saved": True,
                "path": path,
                "size_bytes": len(payload.encode("utf-8")),
            }
        except Exception:
            return {"saved": False, "path": path, "size_bytes": 0}

    def get_handlers(self) -> list[dict]:
        """Return metadata about all registered handlers.

        Returns:
            List of dicts with keys:
                "name" (str): handler name
                "priority" (int): execution priority
        """
        return [
            {"name": h["name"], "priority": h["priority"]}
            for h in self._handlers
        ]
