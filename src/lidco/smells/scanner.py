"""Smell scanner — detect code smells in source text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lidco.smells.catalog import SmellCatalog


@dataclass(frozen=True)
class SmellMatch:
    """A single smell occurrence found in source code."""

    smell_id: str
    file: str
    line: int
    message: str
    severity: str


class SmellScanner:
    """Scans source text for code smells."""

    def __init__(self, catalog: SmellCatalog) -> None:
        self._catalog = catalog

    # -- public API ---------------------------------------------------------

    def scan_text(self, source: str, filename: str = "") -> list[SmellMatch]:
        """Run all built-in checks and return combined matches."""
        matches: list[SmellMatch] = []
        matches.extend(self.scan_for_long_methods(source))
        matches.extend(self.scan_for_magic_numbers(source))
        matches.extend(self.scan_for_deep_nesting(source))
        # Stamp filename onto every match
        if filename:
            matches = [
                SmellMatch(
                    smell_id=m.smell_id,
                    file=filename,
                    line=m.line,
                    message=m.message,
                    severity=m.severity,
                )
                for m in matches
            ]
        return matches

    def scan_for_long_methods(
        self, source: str, threshold: int = 50
    ) -> list[SmellMatch]:
        """Detect functions/methods longer than *threshold* lines."""
        matches: list[SmellMatch] = []
        lines = source.splitlines()
        smell = self._catalog.get("long_method")
        severity = smell.severity if smell else "high"

        func_start: int | None = None
        func_name: str = ""
        indent_level: int = 0

        for idx, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("def "):
                # Close previous function if any
                if func_start is not None:
                    length = idx - func_start
                    if length > threshold:
                        matches.append(
                            SmellMatch(
                                smell_id="long_method",
                                file="",
                                line=func_start + 1,
                                message=f"Function '{func_name}' is {length} lines (threshold {threshold})",
                                severity=severity,
                            )
                        )
                func_start = idx
                indent_level = len(line) - len(stripped)
                match = re.match(r"def\s+(\w+)", stripped)
                func_name = match.group(1) if match else "unknown"

        # Check last function
        if func_start is not None:
            length = len(lines) - func_start
            if length > threshold:
                matches.append(
                    SmellMatch(
                        smell_id="long_method",
                        file="",
                        line=func_start + 1,
                        message=f"Function '{func_name}' is {length} lines (threshold {threshold})",
                        severity=severity,
                    )
                )
        return matches

    def scan_for_magic_numbers(self, source: str) -> list[SmellMatch]:
        """Detect unexplained numeric literals in code."""
        matches: list[SmellMatch] = []
        smell = self._catalog.get("magic_number")
        severity = smell.severity if smell else "medium"
        _trivial = {0, 1, -1, 2, 100}
        pattern = re.compile(r"(?<![\"'\w])(-?\d+\.?\d*)(?![\"'\w])")

        for idx, line in enumerate(source.splitlines()):
            stripped = line.strip()
            # Skip comments, imports, and simple assignments to constants
            if stripped.startswith("#") or stripped.startswith("import "):
                continue
            for m in pattern.finditer(line):
                try:
                    val = float(m.group(1))
                except ValueError:
                    continue
                if val in _trivial:
                    continue
                # Skip if it looks like an index or a well-known constant
                matches.append(
                    SmellMatch(
                        smell_id="magic_number",
                        file="",
                        line=idx + 1,
                        message=f"Magic number {m.group(1)} found",
                        severity=severity,
                    )
                )
        return matches

    def scan_for_deep_nesting(
        self, source: str, threshold: int = 4
    ) -> list[SmellMatch]:
        """Detect lines exceeding *threshold* indent levels."""
        matches: list[SmellMatch] = []
        smell = self._catalog.get("deep_nesting")
        severity = smell.severity if smell else "high"

        for idx, line in enumerate(source.splitlines()):
            if not line.strip():
                continue
            # Count indent by spaces (assume 4-space indent)
            spaces = len(line) - len(line.lstrip())
            depth = spaces // 4
            if depth > threshold:
                matches.append(
                    SmellMatch(
                        smell_id="deep_nesting",
                        file="",
                        line=idx + 1,
                        message=f"Nesting depth {depth} exceeds threshold {threshold}",
                        severity=severity,
                    )
                )
        return matches

    # -- reporting ----------------------------------------------------------

    def summary(self, matches: list[SmellMatch]) -> str:
        """Return a human-readable summary of *matches*."""
        if not matches:
            return "No code smells detected."
        by_sev: dict[str, int] = {}
        for m in matches:
            by_sev[m.severity] = by_sev.get(m.severity, 0) + 1
        total = len(matches)
        parts = [f"{total} smell(s) found:"]
        for sev in ("critical", "high", "medium", "low"):
            count = by_sev.get(sev, 0)
            if count:
                parts.append(f"  {sev}: {count}")
        return "\n".join(parts)
