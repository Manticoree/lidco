"""Code complexity metrics."""
from __future__ import annotations

import re
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ComplexityResult:
    """Complexity metrics for a single function or module."""

    name: str
    file: str
    cyclomatic: int = 0
    cognitive: int = 0
    lines: int = 0
    maintainability: float = 100.0


_BRANCH_PATTERN = re.compile(
    r"\b(if|elif|for|while|except)\b|(?<!\w)(and|or)(?!\w)"
)
_NESTING_OPENERS = re.compile(r"^(\s*)(if|for|while|with|try|def|class)\b")
_FUNC_DEF = re.compile(r"^(\s*)def\s+(\w+)\s*\(")


class ComplexityAnalyzer:
    """Analyze Python source code for complexity metrics."""

    def __init__(self) -> None:
        pass

    # -- single function ---------------------------------------------------

    def analyze_function(
        self,
        source: str,
        name: str = "",
        file: str = "",
    ) -> ComplexityResult:
        lines = len([l for l in source.splitlines() if l.strip()])
        branches = self._count_branches(source)
        cyclomatic = 1 + branches
        nesting = self._count_nesting(source)
        cognitive = branches + nesting
        mi = self._maintainability_index(cyclomatic, lines)
        return ComplexityResult(
            name=name or "<anonymous>",
            file=file,
            cyclomatic=cyclomatic,
            cognitive=cognitive,
            lines=lines,
            maintainability=round(mi, 2),
        )

    # -- helpers -----------------------------------------------------------

    def _count_branches(self, source: str) -> int:
        return len(_BRANCH_PATTERN.findall(source))

    def _count_nesting(self, source: str) -> int:
        max_depth = 0
        for line in source.splitlines():
            stripped = line.rstrip()
            if not stripped:
                continue
            indent = len(stripped) - len(stripped.lstrip())
            # Approximate nesting: 4-space indents
            depth = indent // 4
            if depth > max_depth:
                max_depth = depth
        return max_depth

    def _maintainability_index(self, cyclomatic: int, lines: int) -> float:
        if lines <= 0:
            return 100.0
        # Simplified maintainability index (0-100 scale)
        volume = lines * math.log2(max(cyclomatic, 1) + 1)
        mi = max(0.0, 171.0 - 5.2 * math.log(max(volume, 1)) - 0.23 * cyclomatic - 16.2 * math.log(max(lines, 1)))
        # Normalize to 0-100
        return min(100.0, mi * (100.0 / 171.0))

    # -- module-level analysis ---------------------------------------------

    def analyze_module(self, source: str, file: str = "") -> list[ComplexityResult]:
        results: list[ComplexityResult] = []
        lines = source.splitlines()
        func_starts: list[tuple[int, str, int]] = []

        for i, line in enumerate(lines):
            m = _FUNC_DEF.match(line)
            if m:
                indent_level = len(m.group(1))
                func_starts.append((i, m.group(2), indent_level))

        for idx, (start, fname, base_indent) in enumerate(func_starts):
            # Find end of function
            if idx + 1 < len(func_starts):
                end = func_starts[idx + 1][0]
            else:
                end = len(lines)
            func_source = "\n".join(lines[start:end])
            results.append(self.analyze_function(func_source, name=fname, file=file))

        if not func_starts:
            # Treat entire module as one unit
            results.append(self.analyze_function(source, name="<module>", file=file))

        return results

    def hotspots(
        self,
        results: list[ComplexityResult],
        top_n: int = 10,
    ) -> list[ComplexityResult]:
        sorted_results = sorted(results, key=lambda r: r.cyclomatic, reverse=True)
        return sorted_results[:top_n]

    def summary(self, results: list[ComplexityResult]) -> str:
        if not results:
            return "No results to summarize."
        total = len(results)
        avg_cc = sum(r.cyclomatic for r in results) / total
        avg_mi = sum(r.maintainability for r in results) / total
        max_cc = max(r.cyclomatic for r in results)
        return (
            f"Functions: {total}, "
            f"Avg cyclomatic: {avg_cc:.1f}, "
            f"Max cyclomatic: {max_cc}, "
            f"Avg maintainability: {avg_mi:.1f}"
        )
