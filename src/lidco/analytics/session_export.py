"""Session analytics exporter — Task 441.

Separate from the existing cli/session_exporter.py (which handles conversation
history export).  This module exports analytics/metrics data.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class AnalyticsRecord:
    """Flat record of session analytics data."""

    turn_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    agents_used: list[str] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)
    files_edited: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    error_count: int = 0
    session_id: str = ""
    exported_at: str = ""


class SessionAnalyticsExporter:
    """Collects session analytics and exports to JSON or CSV."""

    def __init__(self, session: Any = None) -> None:
        self._session = session
        self._start_time = time.time()

    def _collect(self) -> AnalyticsRecord:
        """Build an AnalyticsRecord from the current session state."""
        record = AnalyticsRecord(exported_at=datetime.utcnow().isoformat() + "Z")

        if self._session is None:
            return record

        # Turn count
        history = []
        orch = getattr(self._session, "orchestrator", None)
        if orch:
            history = list(getattr(orch, "_conversation_history", []))
        user_turns = [m for m in history if isinstance(m, dict) and m.get("role") == "user"]
        record.turn_count = len(user_turns)

        # Token / cost
        tb = getattr(self._session, "token_budget", None)
        if tb is not None:
            record.total_tokens = (
                getattr(tb, "total_prompt_tokens", 0)
                + getattr(tb, "total_completion_tokens", 0)
            )
            record.total_cost = getattr(tb, "total_cost_usd", 0.0)

        # Agents used — from _agent_stats on CommandRegistry
        cmd_reg = getattr(self._session, "_command_registry", None)
        if cmd_reg is None:
            # Try attribute directly on session
            cmd_reg = getattr(self._session, "command_registry", None)
        if cmd_reg is not None:
            agent_stats = getattr(cmd_reg, "_agent_stats", {})
            record.agents_used = list(agent_stats.keys())

        # Tools called — from session tool_registry
        tool_reg = getattr(self._session, "tool_registry", None)
        if tool_reg is not None:
            all_tools = getattr(tool_reg, "_tools", {})
            record.tools_called = list(all_tools.keys())

        # Files edited — from command registry _edited_files
        if cmd_reg is not None:
            edited = getattr(cmd_reg, "_edited_files", [])
            record.files_edited = list(edited)

        # Errors
        err_hist = getattr(self._session, "_error_history", None)
        if err_hist is not None:
            record.error_count = len(err_hist)

        # Duration
        record.duration_seconds = time.time() - self._start_time

        # Session ID
        record.session_id = getattr(self._session, "session_id", "") or ""

        return record

    # ── export methods ────────────────────────────────────────────────────────

    def export_json(self, path: Path) -> None:
        """Write analytics as structured JSON to *path*."""
        record = self._collect()
        payload = asdict(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def export_csv(self, path: Path) -> None:
        """Write analytics as flat CSV to *path*."""
        record = self._collect()
        payload = asdict(record)
        # Flatten list fields to comma-joined strings
        flat: dict[str, Any] = {}
        for k, v in payload.items():
            if isinstance(v, list):
                flat[k] = ";".join(str(x) for x in v)
            else:
                flat[k] = v

        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(flat.keys()))
            writer.writeheader()
            writer.writerow(flat)

    def export_summary(self) -> str:
        """Return a human-readable summary string."""
        r = self._collect()
        mins = int(r.duration_seconds // 60)
        secs = int(r.duration_seconds % 60)
        agents = ", ".join(r.agents_used) if r.agents_used else "none"
        return (
            f"Session Analytics Summary\n"
            f"  Turns: {r.turn_count}\n"
            f"  Tokens: {r.total_tokens:,}\n"
            f"  Cost: ${r.total_cost:.4f}\n"
            f"  Agents used: {agents}\n"
            f"  Files edited: {len(r.files_edited)}\n"
            f"  Errors: {r.error_count}\n"
            f"  Duration: {mins}m {secs}s\n"
        )
