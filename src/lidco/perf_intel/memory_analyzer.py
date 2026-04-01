"""Memory leak pattern detection in Python source code."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryIssue:
    """A detected memory issue."""

    issue_type: str
    file: str = ""
    line: int = 0
    description: str = ""
    severity: str = "medium"
    pattern: str = ""


class MemoryAnalyzer:
    """Detect memory leak patterns via static analysis."""

    def __init__(self) -> None:
        pass

    def detect_leaks(self, source: str, file: str = "") -> list[MemoryIssue]:
        """Run all detection passes on *source*."""
        results: list[MemoryIssue] = []
        results.extend(self._detect_circular_refs(source, file))
        results.extend(self._detect_growing_collections(source, file))
        results.extend(self._detect_unclosed_resources(source, file))
        return results

    def _detect_circular_refs(
        self, source: str, file: str
    ) -> list[MemoryIssue]:
        """Detect self-referential patterns (``self.x = self``)."""
        results: list[MemoryIssue] = []
        lines = source.splitlines()
        pattern = re.compile(r"self\.(\w+)\s*=\s*self\b")
        for i, line in enumerate(lines):
            m = pattern.search(line)
            if m:
                results.append(
                    MemoryIssue(
                        issue_type="circular_reference",
                        file=file,
                        line=i + 1,
                        description=f"self.{m.group(1)} references self — potential circular ref",
                        severity="high",
                        pattern="self.attr = self",
                    )
                )
        return results

    def _detect_growing_collections(
        self, source: str, file: str
    ) -> list[MemoryIssue]:
        """Detect appends to module/class-level collections (unbounded growth)."""
        results: list[MemoryIssue] = []
        lines = source.splitlines()
        # Look for .append() or .extend() on attributes inside loops
        loop_re = re.compile(r"^\s*(for |while )")
        append_re = re.compile(r"(self\.\w+|[A-Z_]+\w*)\.(?:append|extend)\(")
        for i, line in enumerate(lines):
            if not loop_re.match(line):
                continue
            indent = len(line) - len(line.lstrip())
            for j in range(i + 1, min(i + 40, len(lines))):
                inner = lines[j]
                if inner.strip() == "":
                    continue
                inner_indent = len(inner) - len(inner.lstrip())
                if inner_indent <= indent:
                    break
                m = append_re.search(inner)
                if m:
                    results.append(
                        MemoryIssue(
                            issue_type="growing_collection",
                            file=file,
                            line=j + 1,
                            description=f"'{m.group(0).rstrip('(')}' grows inside loop — potential memory leak",
                            severity="medium",
                            pattern="collection.append in loop",
                        )
                    )
        return results

    def _detect_unclosed_resources(
        self, source: str, file: str
    ) -> list[MemoryIssue]:
        """Detect open() without a with-statement context manager."""
        results: list[MemoryIssue] = []
        lines = source.splitlines()
        open_re = re.compile(r"(\w+)\s*=\s*open\(")
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("with "):
                continue
            m = open_re.search(line)
            if m:
                results.append(
                    MemoryIssue(
                        issue_type="unclosed_resource",
                        file=file,
                        line=i + 1,
                        description=f"open() assigned to '{m.group(1)}' without context manager",
                        severity="high",
                        pattern="f = open(...) without with",
                    )
                )
        return results

    def summary(self, issues: list[MemoryIssue]) -> str:
        """Human-readable summary."""
        if not issues:
            return "No memory issues detected."
        lines = [f"Memory issues: {len(issues)}"]
        for issue in issues:
            lines.append(
                f"  [{issue.severity}] {issue.issue_type} at "
                f"{issue.file}:{issue.line} — {issue.description}"
            )
        return "\n".join(lines)
