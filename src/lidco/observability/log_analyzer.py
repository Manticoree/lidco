"""Q297 -- LogAnalyzer2: ingest, pattern detection, clustering, root-cause."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LogPattern:
    """A detected log pattern."""

    pattern: str
    count: int
    severity: str = "info"
    examples: list[str] = field(default_factory=list)


@dataclass
class ErrorCluster:
    """A cluster of similar error lines."""

    key: str
    count: int
    lines: list[str] = field(default_factory=list)


class LogAnalyzer2:
    """Analyze logs: ingest, detect patterns, cluster errors, suggest root cause."""

    _SEVERITY_RE = re.compile(
        r"\b(ERROR|WARN(?:ING)?|INFO|DEBUG|CRITICAL|FATAL)\b", re.IGNORECASE
    )

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._error_lines: list[str] = []

    # -- ingest ------------------------------------------------------------

    def ingest(self, lines: list[str]) -> int:
        """Ingest log lines.  Returns number of lines ingested."""
        count = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            self._lines.append(stripped)
            m = self._SEVERITY_RE.search(stripped)
            if m and m.group(1).upper() in ("ERROR", "CRITICAL", "FATAL"):
                self._error_lines.append(stripped)
            count += 1
        return count

    # -- analysis ----------------------------------------------------------

    def detect_patterns(self) -> list[LogPattern]:
        """Detect recurring patterns in ingested lines."""
        severity_counts: dict[str, int] = Counter()
        severity_examples: dict[str, list[str]] = {}
        for line in self._lines:
            m = self._SEVERITY_RE.search(line)
            sev = m.group(1).upper() if m else "UNKNOWN"
            severity_counts[sev] += 1
            severity_examples.setdefault(sev, [])
            if len(severity_examples[sev]) < 3:
                severity_examples[sev].append(line)

        patterns: list[LogPattern] = []
        for sev, cnt in severity_counts.most_common():
            patterns.append(
                LogPattern(
                    pattern=sev,
                    count=cnt,
                    severity=sev.lower(),
                    examples=severity_examples.get(sev, []),
                )
            )
        return patterns

    def cluster_errors(self) -> list[ErrorCluster]:
        """Cluster error lines by normalised message."""
        buckets: dict[str, list[str]] = {}
        for line in self._error_lines:
            key = self._normalise(line)
            buckets.setdefault(key, []).append(line)

        clusters = [
            ErrorCluster(key=k, count=len(v), lines=v)
            for k, v in buckets.items()
        ]
        clusters.sort(key=lambda c: c.count, reverse=True)
        return clusters

    def suggest_root_cause(self, error: str) -> str:
        """Return a best-effort root-cause suggestion for *error*."""
        lower = error.lower()
        if "timeout" in lower:
            return "Possible network or service timeout — check upstream latency."
        if "connection" in lower and ("refused" in lower or "reset" in lower):
            return "Connection refused/reset — verify the target service is running."
        if "permission" in lower or "denied" in lower:
            return "Permission denied — check file/service ACLs and credentials."
        if "memory" in lower or "oom" in lower:
            return "Out of memory — consider increasing limits or profiling allocations."
        if "disk" in lower or "no space" in lower:
            return "Disk space exhausted — free space or expand volume."
        return "Unknown root cause — inspect the full stack trace for details."

    def summary(self) -> dict[str, Any]:
        """Return summary statistics."""
        return {
            "total_lines": len(self._lines),
            "error_lines": len(self._error_lines),
            "patterns": len(self.detect_patterns()),
            "error_clusters": len(self.cluster_errors()),
        }

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _normalise(line: str) -> str:
        """Normalise a log line into a cluster key (strip numbers/hex)."""
        s = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*\S*", "<TS>", line)
        s = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", s)
        s = re.sub(r"\b\d+\b", "<N>", s)
        return s.strip()
