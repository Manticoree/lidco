"""Coverage trend tracker — Task 440."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


@dataclass
class CoverageSnapshot:
    """Coverage measurement at a point in time."""

    commit_hash: str
    timestamp: str           # ISO-8601 UTC
    overall_pct: float
    file_coverages: dict[str, float] = field(default_factory=dict)


class CoverageTrendTracker:
    """Records coverage over time and detects regressions."""

    def __init__(self, project_dir: Path | None = None) -> None:
        self._project_dir = project_dir or Path.cwd()

    # ── persistence ──────────────────────────────────────────────────────────

    @property
    def _store_path(self) -> Path:
        return self._project_dir / ".lidco" / "analytics" / "coverage_history.json"

    def record(self, snapshot: CoverageSnapshot) -> None:
        """Append *snapshot* to the history file."""
        history = self.load_history(last_n=None)  # type: ignore[arg-type]
        history.append(snapshot)

        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                "commit_hash": s.commit_hash,
                "timestamp": s.timestamp,
                "overall_pct": s.overall_pct,
                "file_coverages": s.file_coverages,
            }
            for s in history
        ]
        self._store_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_history(self, last_n: int | None = 20) -> list[CoverageSnapshot]:
        """Return the last *last_n* snapshots (all if *last_n* is None)."""
        try:
            data = json.loads(self._store_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return []

        snapshots = [
            CoverageSnapshot(
                commit_hash=item.get("commit_hash", ""),
                timestamp=item.get("timestamp", ""),
                overall_pct=float(item.get("overall_pct", 0.0)),
                file_coverages=item.get("file_coverages", {}),
            )
            for item in data
            if isinstance(item, dict)
        ]
        if last_n is None:
            return snapshots
        return snapshots[-last_n:]

    # ── analysis ─────────────────────────────────────────────────────────────

    def detect_regressions(self, threshold: float = 2.0) -> list[tuple[str, float]]:
        """Return files where coverage dropped by more than *threshold* percent.

        Compares the two most recent snapshots that both include each file.
        Returns list of (file_path, drop_pct) sorted by drop descending.
        """
        history = self.load_history(last_n=2)
        if len(history) < 2:
            return []

        prev, curr = history[-2], history[-1]
        regressions: list[tuple[str, float]] = []
        for file_path, curr_cov in curr.file_coverages.items():
            prev_cov = prev.file_coverages.get(file_path)
            if prev_cov is not None:
                drop = prev_cov - curr_cov
                if drop > threshold:
                    regressions.append((file_path, drop))

        return sorted(regressions, key=lambda x: -x[1])

    def trend_line(self, last_n: int = 10) -> str:
        """Return a Unicode sparkline of overall coverage over the last *last_n* snapshots."""
        history = self.load_history(last_n=last_n)
        values = [s.overall_pct for s in history]
        if not values:
            return ""

        min_v = min(values)
        max_v = max(values)
        span = max_v - min_v

        chars: list[str] = []
        for v in values:
            if span == 0:
                idx = len(_SPARK_BLOCKS) - 1
            else:
                idx = int((v - min_v) / span * (len(_SPARK_BLOCKS) - 1))
            chars.append(_SPARK_BLOCKS[idx])
        return "".join(chars)
