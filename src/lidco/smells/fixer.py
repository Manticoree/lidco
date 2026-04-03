"""Smell fixer — suggest or apply fixes for detected smells."""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from lidco.smells.catalog import SmellCatalog
from lidco.smells.scanner import SmellMatch


@dataclass(frozen=True)
class FixResult:
    """Result of applying a fix to a smell."""

    smell_id: str
    original: str
    fixed: str
    description: str


class SmellFixer:
    """Applies automated fixes for code smells where possible."""

    def __init__(self, catalog: SmellCatalog) -> None:
        self._catalog = catalog

    def fix(self, match: SmellMatch, source: str) -> FixResult | None:
        """Attempt to fix *match* in *source*. Returns ``None`` if no fix."""
        handler = self._fix_handlers.get(match.smell_id)
        if handler is None:
            return None
        return handler(self, match, source)

    def preview(self, match: SmellMatch, source: str) -> str:
        """Return a unified diff preview of the proposed fix."""
        result = self.fix(match, source)
        if result is None:
            return "No automated fix available."
        orig_lines = result.original.splitlines(keepends=True)
        fixed_lines = result.fixed.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            fixed_lines,
            fromfile="original",
            tofile="fixed",
            lineterm="",
        )
        return "".join(diff) or "No changes."

    def batch_fix(
        self, matches: list[SmellMatch], source: str
    ) -> list[FixResult]:
        """Apply fixes for all *matches* that have automated fixers."""
        results: list[FixResult] = []
        current = source
        for m in matches:
            result = self.fix(m, current)
            if result is not None:
                current = result.fixed
                results.append(result)
        return results

    # -- individual fixers --------------------------------------------------

    def _fix_magic_number(self, match: SmellMatch, source: str) -> FixResult | None:
        """Replace a magic number with a named constant."""
        lines = source.splitlines()
        line_idx = match.line - 1
        if line_idx < 0 or line_idx >= len(lines):
            return None

        import re

        line = lines[line_idx]
        # Find the first non-trivial number
        m = re.search(r"(?<![\"'\w])(-?\d+\.?\d*)(?![\"'\w])", line)
        if m is None:
            return None

        value = m.group(1)
        const_name = f"CONST_{value.replace('.', '_').replace('-', 'NEG_')}"
        new_line = line[: m.start()] + const_name + line[m.end() :]

        new_lines = list(lines)
        # Insert constant definition before the line
        indent = ""
        new_lines.insert(line_idx, f"{indent}{const_name} = {value}")
        new_lines[line_idx + 1] = new_line

        fixed = "\n".join(new_lines)
        return FixResult(
            smell_id="magic_number",
            original=source,
            fixed=fixed,
            description=f"Extracted magic number {value} to constant {const_name}",
        )

    def _fix_commented_code(self, match: SmellMatch, source: str) -> FixResult | None:
        """Remove commented-out code blocks."""
        lines = source.splitlines()
        line_idx = match.line - 1
        if line_idx < 0 or line_idx >= len(lines):
            return None

        new_lines = [l for i, l in enumerate(lines) if i != line_idx]
        fixed = "\n".join(new_lines)
        return FixResult(
            smell_id="commented_code",
            original=source,
            fixed=fixed,
            description=f"Removed commented-out code at line {match.line}",
        )

    _fix_handlers: dict = {
        "magic_number": _fix_magic_number,
        "commented_code": _fix_commented_code,
    }
