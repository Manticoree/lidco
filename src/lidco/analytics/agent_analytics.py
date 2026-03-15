"""Agent performance analytics — Task 438."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AgentStats:
    """Accumulated statistics for a single agent."""

    agent_name: str
    total_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_duration_ms: float = 0.0
    success_rate: float = 1.0
    error_count: int = 0

    # internal accumulator not exposed to callers
    _total_duration_ms: float = 0.0


class AgentAnalytics:
    """Tracks and persists per-agent call statistics."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._stats: dict[str, AgentStats] = {}
        self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    @property
    def _store_path(self) -> Path:
        return self._project_dir / ".lidco" / "analytics" / "agent_stats.json"

    def _load(self) -> None:
        """Load persisted stats if available."""
        try:
            data = json.loads(self._store_path.read_text(encoding="utf-8"))
            for name, raw in data.items():
                stats = AgentStats(
                    agent_name=name,
                    total_calls=raw.get("total_calls", 0),
                    total_tokens=raw.get("total_tokens", 0),
                    total_cost_usd=raw.get("total_cost_usd", 0.0),
                    avg_duration_ms=raw.get("avg_duration_ms", 0.0),
                    success_rate=raw.get("success_rate", 1.0),
                    error_count=raw.get("error_count", 0),
                    _total_duration_ms=raw.get("_total_duration_ms", 0.0),
                )
                self._stats[name] = stats
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

    def _save(self) -> None:
        """Persist stats to disk."""
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            payload: dict[str, Any] = {}
            for name, s in self._stats.items():
                payload[name] = {
                    "total_calls": s.total_calls,
                    "total_tokens": s.total_tokens,
                    "total_cost_usd": s.total_cost_usd,
                    "avg_duration_ms": s.avg_duration_ms,
                    "success_rate": s.success_rate,
                    "error_count": s.error_count,
                    "_total_duration_ms": s._total_duration_ms,
                }
            self._store_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass

    # ── recording ────────────────────────────────────────────────────────────

    def record_call(
        self,
        agent: str,
        tokens_in: int,
        tokens_out: int,
        cost: float,
        duration_ms: float,
        success: bool,
    ) -> None:
        """Accumulate one call's metrics for *agent*."""
        if agent not in self._stats:
            self._stats[agent] = AgentStats(agent_name=agent)

        s = self._stats[agent]
        s.total_calls += 1
        s.total_tokens += tokens_in + tokens_out
        s.total_cost_usd += cost
        s._total_duration_ms += duration_ms
        s.avg_duration_ms = s._total_duration_ms / s.total_calls
        if not success:
            s.error_count += 1
        s.success_rate = (s.total_calls - s.error_count) / s.total_calls

        self._save()

    # ── querying ─────────────────────────────────────────────────────────────

    def get_stats(self, agent: str | None = None) -> list[AgentStats]:
        """Return stats for all agents or a specific one."""
        if agent is not None:
            if agent in self._stats:
                return [self._stats[agent]]
            return []
        return list(self._stats.values())

    def top_by_cost(self, n: int = 5) -> list[AgentStats]:
        """Return top-*n* agents sorted by total cost descending."""
        return sorted(self._stats.values(), key=lambda s: s.total_cost_usd, reverse=True)[:n]

    def top_by_calls(self, n: int = 5) -> list[AgentStats]:
        """Return top-*n* agents sorted by call count descending."""
        return sorted(self._stats.values(), key=lambda s: s.total_calls, reverse=True)[:n]

    def top_by_time(self, n: int = 5) -> list[AgentStats]:
        """Return top-*n* agents sorted by avg duration descending."""
        return sorted(self._stats.values(), key=lambda s: s.avg_duration_ms, reverse=True)[:n]

    # ── Rich table rendering ──────────────────────────────────────────────────

    def render_table(
        self,
        sort: str = "cost",
        top: int = 10,
    ) -> Any:
        """Return a Rich Table of agent analytics."""
        from rich.table import Table

        if sort == "calls":
            rows = self.top_by_calls(top)
        elif sort == "time":
            rows = self.top_by_time(top)
        else:
            rows = self.top_by_cost(top)

        table = Table(title="Agent Analytics", show_header=True, header_style="bold cyan")
        table.add_column("Agent", style="bold")
        table.add_column("Calls", justify="right")
        table.add_column("Tokens", justify="right")
        table.add_column("Cost (USD)", justify="right", style="green")
        table.add_column("Avg ms", justify="right")
        table.add_column("Success%", justify="right")
        table.add_column("Errors", justify="right", style="red")

        for s in rows:
            table.add_row(
                s.agent_name,
                str(s.total_calls),
                f"{s.total_tokens:,}",
                f"${s.total_cost_usd:.4f}",
                f"{s.avg_duration_ms:.0f}",
                f"{s.success_rate * 100:.1f}%",
                str(s.error_count),
            )

        return table
