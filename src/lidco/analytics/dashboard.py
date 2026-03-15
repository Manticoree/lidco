"""Real-time cost dashboard — Task 437."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


_SPARK_BLOCKS = " ▁▂▃▄▅▆▇█"


@dataclass
class CostSample:
    """A single cost measurement from a model call."""

    timestamp: float          # time.time()
    agent: str
    tokens_in: int
    tokens_out: int
    cost_usd: float


class CostDashboard:
    """Collects and visualises real-time LLM cost data."""

    _MAX_SAMPLES = 1000

    def __init__(self, session: Any = None) -> None:
        self._session = session
        self._samples: list[CostSample] = []

    # ── data ingestion ────────────────────────────────────────────────────────

    def record(self, sample: CostSample) -> None:
        """Add *sample*; keeps last _MAX_SAMPLES entries."""
        new_samples = self._samples + [sample]
        if len(new_samples) > self._MAX_SAMPLES:
            new_samples = new_samples[-self._MAX_SAMPLES:]
        self._samples = new_samples

    # ── aggregation helpers ───────────────────────────────────────────────────

    def total_cost(self) -> float:
        return sum(s.cost_usd for s in self._samples)

    def total_tokens_in(self) -> int:
        return sum(s.tokens_in for s in self._samples)

    def total_tokens_out(self) -> int:
        return sum(s.tokens_out for s in self._samples)

    def per_agent_cost(self) -> dict[str, float]:
        """Return mapping of agent_name → total_cost_usd."""
        result: dict[str, float] = {}
        for s in self._samples:
            result[s.agent] = result.get(s.agent, 0.0) + s.cost_usd
        return result

    def last_n_turn_costs(self, n: int = 10) -> list[float]:
        """Return the cost for the last *n* samples."""
        return [s.cost_usd for s in self._samples[-n:]]

    # ── sparkline ─────────────────────────────────────────────────────────────

    @staticmethod
    def sparkline(values: list[float], width: int = 20) -> str:
        """Render a Unicode sparkline for *values* scaled to *width* chars.

        Uses the block characters ▁▂▃▄▅▆▇█.  Returns a string of
        exactly ``min(len(values), width)`` block characters.
        """
        if not values:
            return ""

        # Sample / truncate to width
        if len(values) > width:
            # Downsample: take evenly spaced indices
            step = len(values) / width
            values = [values[int(i * step)] for i in range(width)]

        min_v = min(values)
        max_v = max(values)
        span = max_v - min_v

        blocks = _SPARK_BLOCKS[1:]  # 8 non-blank blocks

        chars: list[str] = []
        for v in values:
            if span == 0:
                idx = 0
            else:
                idx = int((v - min_v) / span * (len(blocks) - 1))
            chars.append(blocks[idx])
        return "".join(chars)

    # ── Rich layout ───────────────────────────────────────────────────────────

    def render(self) -> Any:
        """Return a Rich Layout representing the current dashboard."""
        from rich.layout import Layout
        from rich.panel import Panel
        from rich.progress import BarColumn, Progress, TextColumn
        from rich.table import Table
        from rich.text import Text

        layout = Layout()
        layout.split_column(
            Layout(name="top", ratio=1),
            Layout(name="middle", ratio=2),
            Layout(name="bottom", ratio=1),
        )

        # ── Top: session totals ───────────────────────────────────────────────
        total_cost = self.total_cost()
        total_in = self.total_tokens_in()
        total_out = self.total_tokens_out()
        top_text = (
            f"Session cost: [bold green]${total_cost:.4f}[/bold green]  |  "
            f"Tokens in: [cyan]{total_in:,}[/cyan]  |  "
            f"Tokens out: [yellow]{total_out:,}[/yellow]"
        )
        layout["top"].update(Panel(Text.from_markup(top_text), title="Session Totals"))

        # ── Middle: per-agent cost as progress bars ───────────────────────────
        agent_costs = self.per_agent_cost()
        max_cost = max(agent_costs.values(), default=1.0) or 1.0

        progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            TextColumn("[green]{task.fields[cost_str]}"),
        )
        for agent, cost in sorted(agent_costs.items(), key=lambda x: -x[1]):
            progress.add_task(
                agent,
                total=max_cost,
                completed=cost,
                cost_str=f"${cost:.4f}",
            )

        layout["middle"].update(Panel(progress, title="Per-Agent Cost Breakdown"))

        # ── Bottom: last-10-turns sparkline ───────────────────────────────────
        last_costs = self.last_n_turn_costs(10)
        spark = self.sparkline(last_costs, width=20)
        cost_values = ", ".join(f"${c:.4f}" for c in last_costs)
        bottom_text = f"[bold]{spark}[/bold]\n{cost_values}"
        layout["bottom"].update(Panel(Text.from_markup(bottom_text), title="Last 10 Turns Cost Trend"))

        return layout
