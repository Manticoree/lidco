"""Technical debt detection and tracking."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DebtItem:
    """A single technical debt marker found in source code."""

    file: str
    line: int
    marker: str
    text: str
    severity: str = "medium"
    estimated_hours: float = 0.5


@dataclass(frozen=True)
class DebtReport:
    """Aggregated debt report."""

    items: tuple[DebtItem, ...] = ()
    total_hours: float = 0.0
    by_severity: dict[str, int] = field(default_factory=dict)


_DEFAULT_MARKERS = ["TODO", "FIXME", "HACK", "XXX"]


class TechDebtTracker:
    """Scan source text for debt markers and produce reports."""

    def __init__(self, markers: list[str] | None = None) -> None:
        self._markers = list(markers) if markers is not None else list(_DEFAULT_MARKERS)
        self._items: list[DebtItem] = []
        self._pattern = re.compile(
            r"\b(" + "|".join(re.escape(m) for m in self._markers) + r")\b\s*:?\s*(.*)",
            re.IGNORECASE,
        )

    # -- scanning ----------------------------------------------------------

    def scan_text(self, text: str, file_path: str = "") -> list[DebtItem]:
        found: list[DebtItem] = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = self._pattern.search(line)
            if match:
                marker = match.group(1).upper()
                description = match.group(2).strip()
                severity = self._severity_for(marker)
                item = DebtItem(
                    file=file_path,
                    line=lineno,
                    marker=marker,
                    text=description,
                    severity=severity,
                )
                found.append(item)
        return found

    def scan_file(self, path: str) -> list[DebtItem]:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        items = self.scan_text(text, file_path=path)
        self._items.extend(items)
        return items

    # -- item management ---------------------------------------------------

    def add_item(self, item: DebtItem) -> None:
        self._items.append(item)

    def clear(self) -> None:
        self._items = []

    # -- reporting ---------------------------------------------------------

    def report(self) -> DebtReport:
        total = sum(i.estimated_hours for i in self._items)
        counts: dict[str, int] = {}
        for item in self._items:
            counts[item.severity] = counts.get(item.severity, 0) + 1
        return DebtReport(
            items=tuple(self._items),
            total_hours=round(total, 2),
            by_severity=counts,
        )

    def by_file(self) -> dict[str, list[DebtItem]]:
        result: dict[str, list[DebtItem]] = {}
        for item in self._items:
            result.setdefault(item.file, []).append(item)
        return result

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _severity_for(marker: str) -> str:
        if marker in ("FIXME", "XXX"):
            return "high"
        if marker == "HACK":
            return "medium"
        return "low"
