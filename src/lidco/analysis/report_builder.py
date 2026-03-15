"""Unified analysis report builder — Task 360."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnalysisEntry:
    """A single normalized finding from any analyzer."""
    category: str       # e.g. "complexity", "security", "imports"
    kind: str           # enum value string
    severity: str       # "critical" | "high" | "medium" | "low" | "info"
    file: str
    line: int
    message: str


@dataclass
class UnifiedReport:
    entries: list[AnalysisEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(self, entry: AnalysisEntry) -> None:
        self.entries.append(entry)

    def by_severity(self, severity: str) -> list[AnalysisEntry]:
        return [e for e in self.entries if e.severity == severity]

    def by_category(self, category: str) -> list[AnalysisEntry]:
        return [e for e in self.entries if e.category == category]

    def by_file(self, file: str) -> list[AnalysisEntry]:
        return [e for e in self.entries if e.file == file]

    @property
    def critical_count(self) -> int:
        return sum(1 for e in self.entries if e.severity == "critical")

    @property
    def high_count(self) -> int:
        return sum(1 for e in self.entries if e.severity == "high")

    @property
    def total(self) -> int:
        return len(self.entries)

    def summary(self) -> str:
        parts = []
        for sev in ("critical", "high", "medium", "low", "info"):
            count = sum(1 for e in self.entries if e.severity == sev)
            if count:
                parts.append(f"{sev}: {count}")
        return ", ".join(parts) if parts else "no issues"


# Severity mappings per category
_SEVERITY_MAP: dict[str, dict[str, str]] = {
    "security": {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
    },
    "complexity": {
        "high": "high",
        "medium": "medium",
        "low": "info",
    },
    "imports": {
        "unused_import": "low",
        "star_import": "medium",
        "duplicate_import": "low",
    },
    "exceptions": {
        "bare_except": "medium",
        "broad_except": "low",
        "swallowed_exception": "medium",
        "reraise_lost": "low",
    },
    "strings": {
        "hardcoded_url": "low",
        "hardcoded_ip": "medium",
        "hardcoded_path": "low",
        "long_string": "info",
        "todo_fixme": "info",
    },
    "naming": {
        "function_name": "low",
        "class_name": "low",
    },
    "flow": {
        "unreachable_code": "medium",
        "missing_return": "low",
        "inconsistent_return": "medium",
        "infinite_loop": "high",
    },
    "variables": {
        "unused_variable": "low",
        "shadowed_variable": "low",
        "global_misuse": "medium",
    },
    "classes": {
        "deep_inheritance": "medium",
        "too_many_methods": "medium",
        "god_class": "high",
        "no_docstring": "info",
    },
    "dead_code": {
        "dead_function": "low",
        "dead_class": "low",
        "dead_variable": "info",
    },
}


def _resolve_severity(category: str, kind: str) -> str:
    cat_map = _SEVERITY_MAP.get(category, {})
    # Try exact match first, then prefix match
    for key, sev in cat_map.items():
        if kind == key or kind in key or key in kind:
            return sev
    return "info"


class ReportBuilder:
    """Aggregate findings from multiple analyzers into a UnifiedReport."""

    def __init__(self) -> None:
        self._report = UnifiedReport()

    def add_findings(
        self,
        category: str,
        findings: list[Any],
        *,
        kind_attr: str = "kind",
        file_attr: str = "file",
        line_attr: str = "line",
        detail_attr: str = "detail",
        severity_attr: str | None = None,
    ) -> "ReportBuilder":
        """
        Normalize a list of issue objects from any analyzer.

        Parameters
        ----------
        category    : analysis domain (e.g. "security", "imports")
        findings    : list of issue dataclass instances
        kind_attr   : attribute name for the kind/enum field
        file_attr   : attribute name for file path
        line_attr   : attribute name for line number
        detail_attr : attribute name for human-readable message
        severity_attr: if the issue has its own severity field, use it
        """
        for issue in findings:
            raw_kind = getattr(issue, kind_attr)
            kind_str = raw_kind.value if hasattr(raw_kind, "value") else str(raw_kind)

            if severity_attr:
                raw_sev = getattr(issue, severity_attr, None)
                sev = raw_sev.value if hasattr(raw_sev, "value") else str(raw_sev) if raw_sev else "info"
                sev = sev.lower()
            else:
                sev = _resolve_severity(category, kind_str)

            entry = AnalysisEntry(
                category=category,
                kind=kind_str,
                severity=sev,
                file=getattr(issue, file_attr, ""),
                line=getattr(issue, line_attr, 0),
                message=getattr(issue, detail_attr, ""),
            )
            self._report.add(entry)
        return self

    def set_metadata(self, key: str, value: Any) -> "ReportBuilder":
        self._report.metadata[key] = value
        return self

    def build(self) -> UnifiedReport:
        return self._report
