"""Error pattern visualisation — Task 443."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lidco.core.errors import ErrorHistory, ErrorRecord


_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


class ErrorViz:
    """Visualises ErrorHistory as ASCII charts."""

    # ── data aggregation ──────────────────────────────────────────────────────

    def frequency_by_time(
        self,
        history: ErrorHistory,
        bucket_minutes: int = 60,
    ) -> list[tuple[str, int]]:
        """Return (time_bucket_label, count) pairs aggregated by *bucket_minutes*."""
        records = history.get_recent(len(history._records))

        if not records:
            return []

        buckets: dict[str, int] = {}
        for rec in records:
            ts = rec.timestamp
            # Truncate to bucket boundary
            bucket_start = ts.replace(
                minute=(ts.minute // bucket_minutes) * bucket_minutes,
                second=0,
                microsecond=0,
            )
            label = bucket_start.strftime("%H:%M")
            buckets[label] = buckets.get(label, 0) + rec.occurrence_count

        # Return in chronological order
        return sorted(buckets.items())

    def frequency_by_type(self, history: ErrorHistory) -> dict[str, int]:
        """Return mapping of error_type → total occurrence count."""
        result: dict[str, int] = {}
        for rec in history._records:
            result[rec.error_type] = result.get(rec.error_type, 0) + rec.occurrence_count
        return result

    # ── ASCII chart renderers ─────────────────────────────────────────────────

    def ascii_bar_chart(
        self,
        data: dict[str, int],
        title: str = "Error Frequency",
        width: int = 40,
    ) -> str:
        """Return an ASCII horizontal bar chart string."""
        if not data:
            return f"{title}\n(no data)"

        max_val = max(data.values()) or 1
        lines = [title, ""]

        label_width = max(len(k) for k in data) + 1

        for label, count in sorted(data.items(), key=lambda x: -x[1]):
            bar_len = int(count / max_val * width)
            bar = "█" * bar_len
            lines.append(f"{label:<{label_width}} {bar} {count}")

        return "\n".join(lines)

    def time_series_chart(
        self,
        data: list[tuple[str, int]],
        title: str = "Errors Over Time",
        width: int = 60,
    ) -> str:
        """Return an ASCII time-series chart using ▁▂▃▄▅▆▇█ blocks."""
        if not data:
            return f"{title}\n(no data)"

        values = [count for _, count in data]
        labels = [label for label, _ in data]

        max_val = max(values) or 1
        min_val = min(values)
        span = max_val - min_val

        # Build sparkline
        chars: list[str] = []
        for v in values:
            if span == 0:
                idx = len(_SPARK_BLOCKS) - 1
            else:
                idx = int((v - min_val) / span * (len(_SPARK_BLOCKS) - 1))
            chars.append(_SPARK_BLOCKS[idx])

        spark = "".join(chars)

        # Build label axis (show first, middle, last)
        n = len(labels)
        if n >= 3:
            axis = f"{labels[0]:<10}{'':>{width//2 - 10}}{labels[n//2]:<10}{'':>{width//2 - 10}}{labels[-1]}"
        elif n == 2:
            axis = f"{labels[0]:<{width//2}}{labels[-1]}"
        else:
            axis = labels[0] if labels else ""

        return f"{title}\n{spark}\n{axis}"

    # ── combined Rich Panel ────────────────────────────────────────────────────

    def render(self, history: ErrorHistory) -> Any:
        """Return a Rich Panel combining type and time visualisations."""
        from rich.panel import Panel
        from rich.text import Text

        by_type = self.frequency_by_type(history)
        by_time = self.frequency_by_time(history)

        bar_chart = self.ascii_bar_chart(by_type, title="By Error Type", width=30)
        time_chart = self.time_series_chart(by_time, title="By Hour", width=40)

        combined = f"{bar_chart}\n\n{time_chart}"
        return Panel(Text(combined), title="Error Pattern Visualisation")
