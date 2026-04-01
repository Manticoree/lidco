"""Git log analysis for file churn."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ChurnRecord:
    """Change frequency record for a single file."""

    file: str
    change_count: int = 0
    authors: tuple[str, ...] = ()
    last_changed: float = 0.0


class ChurnAnalyzer:
    """Track and report file change frequency."""

    def __init__(self) -> None:
        self._changes: dict[str, list[dict[str, object]]] = {}

    def add_change(
        self,
        file: str,
        author: str = "",
        timestamp: float = 0.0,
    ) -> None:
        ts = timestamp if timestamp > 0 else time.time()
        self._changes.setdefault(file, []).append(
            {"author": author, "timestamp": ts}
        )

    def _build_record(self, file: str) -> ChurnRecord:
        entries = self._changes.get(file, [])
        authors = tuple(sorted({str(e["author"]) for e in entries if e["author"]}))
        last = max((float(e["timestamp"]) for e in entries), default=0.0) if entries else 0.0  # type: ignore[arg-type]
        return ChurnRecord(
            file=file,
            change_count=len(entries),
            authors=authors,
            last_changed=last,
        )

    def top_churned(self, n: int = 10) -> list[ChurnRecord]:
        records = [self._build_record(f) for f in self._changes]
        records.sort(key=lambda r: r.change_count, reverse=True)
        return records[:n]

    def author_distribution(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entries in self._changes.values():
            for entry in entries:
                author = str(entry["author"])
                if author:
                    counts[author] = counts.get(author, 0) + 1
        return counts

    def file_risk_score(self, file: str) -> float:
        entries = self._changes.get(file, [])
        if not entries:
            return 0.0
        count = len(entries)
        num_authors = len({str(e["author"]) for e in entries if e["author"]})
        # Higher churn and more authors = higher risk
        return round(count * (1 + num_authors * 0.1), 2)

    def summary(self) -> str:
        total_files = len(self._changes)
        total_changes = sum(len(v) for v in self._changes.values())
        if total_files == 0:
            return "No churn data."
        top = self.top_churned(3)
        top_names = ", ".join(r.file for r in top)
        return (
            f"Files: {total_files}, "
            f"Total changes: {total_changes}, "
            f"Top churned: {top_names}"
        )

    def clear(self) -> None:
        self._changes = {}
