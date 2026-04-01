"""Explain code blocks at various detail levels."""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass


class DetailLevel(str, enum.Enum):
    """Level of explanation detail."""

    BRIEF = "brief"
    DETAILED = "detailed"
    ELI5 = "eli5"


@dataclass(frozen=True)
class CodeExplanation:
    """An explanation of a code block."""

    code: str
    level: DetailLevel
    summary: str
    line_annotations: tuple[tuple[int, str], ...] = ()
    complexity_note: str = ""


class CodeExplainer:
    """Explain code blocks at various detail levels."""

    def __init__(self) -> None:
        self._keywords = {
            "def": "function definition",
            "class": "class definition",
            "if": "conditional check",
            "for": "loop iteration",
            "while": "loop",
            "return": "return value",
            "import": "module import",
            "try": "error handling",
            "with": "context manager",
            "yield": "generator yield",
            "async": "async operation",
            "raise": "raise exception",
        }

    def explain(self, code: str, level: DetailLevel = DetailLevel.BRIEF) -> CodeExplanation:
        """Explain a code block at the given detail level."""
        lines = code.strip().splitlines()
        if not lines:
            return CodeExplanation(code=code, level=level, summary="Empty code block.")

        constructs = self._detect_constructs(lines)
        annotations = tuple(self._annotate(lines))

        if level == DetailLevel.BRIEF:
            summary = self._brief_summary(lines, constructs)
        elif level == DetailLevel.DETAILED:
            summary = self._detailed_summary(lines, constructs, annotations)
        else:
            summary = self._eli5_summary(lines, constructs)

        complexity = self.complexity_estimate(code)

        return CodeExplanation(
            code=code,
            level=level,
            summary=summary,
            line_annotations=annotations,
            complexity_note=complexity,
        )

    def explain_function(self, code: str) -> CodeExplanation:
        """Extract function purpose, params, and return info."""
        lines = code.strip().splitlines()
        func_name = ""
        params: list[str] = []
        has_return = False
        docstring = ""

        for line in lines:
            stripped = line.strip()
            match = re.match(r"(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)", stripped)
            if match:
                func_name = match.group(1)
                raw_params = match.group(2)
                params = [p.strip() for p in raw_params.split(",") if p.strip() and p.strip() != "self"]
            if "return " in stripped:
                has_return = True
            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring = stripped.strip("\"'").strip()

        parts = []
        if func_name:
            parts.append(f"Function '{func_name}'")
        else:
            parts.append("Code block")
        if params:
            parts.append(f"takes parameters: {', '.join(params)}")
        if has_return:
            parts.append("returns a value")
        if docstring:
            parts.append(f"purpose: {docstring}")

        summary = "; ".join(parts) + "."
        annotations = tuple(self._annotate(lines))

        return CodeExplanation(
            code=code,
            level=DetailLevel.DETAILED,
            summary=summary,
            line_annotations=annotations,
        )

    def annotate_lines(self, code: str) -> list[tuple[int, str]]:
        """Per-line brief comments."""
        lines = code.strip().splitlines()
        return self._annotate(lines)

    def complexity_estimate(self, code: str) -> str:
        """Estimate and describe complexity."""
        lines = code.strip().splitlines()
        nesting = 0
        max_nesting = 0
        loop_count = 0
        branch_count = 0

        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            level = indent // 4
            if level > max_nesting:
                max_nesting = level
            for kw in ("for ", "while "):
                if stripped.startswith(kw):
                    loop_count += 1
            if stripped.startswith("if ") or stripped.startswith("elif "):
                branch_count += 1

        if loop_count == 0 and branch_count == 0:
            return "O(1) — constant time, no loops or branches."
        if loop_count == 1 and max_nesting <= 2:
            return "O(n) — linear, single loop."
        if loop_count >= 2 and max_nesting >= 3:
            return "O(n^2) or higher — nested loops detected."
        if loop_count >= 2:
            return "O(n*m) — multiple loops."
        return f"Moderate — {loop_count} loop(s), {branch_count} branch(es), max nesting {max_nesting}."

    def _detect_constructs(self, lines: list[str]) -> list[str]:
        found: list[str] = []
        for line in lines:
            stripped = line.strip()
            for kw, desc in self._keywords.items():
                if stripped.startswith(kw + " ") or stripped.startswith(kw + "("):
                    if desc not in found:
                        found.append(desc)
        return found

    def _annotate(self, lines: list[str]) -> list[tuple[int, str]]:
        result: list[tuple[int, str]] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                comment = "comment or blank"
            else:
                comment = "code"
                for kw, desc in self._keywords.items():
                    if stripped.startswith(kw + " ") or stripped.startswith(kw + "("):
                        comment = desc
                        break
            result.append((i + 1, comment))
        return result

    def _brief_summary(self, lines: list[str], constructs: list[str]) -> str:
        total = len(lines)
        if constructs:
            return f"{total} line(s) with: {', '.join(constructs)}."
        return f"{total} line(s) of code."

    def _detailed_summary(
        self, lines: list[str], constructs: list[str], annotations: tuple[tuple[int, str], ...]
    ) -> str:
        total = len(lines)
        parts = [f"{total} line(s)."]
        if constructs:
            parts.append(f"Contains: {', '.join(constructs)}.")
        parts.append(f"{len(annotations)} annotated line(s).")
        return " ".join(parts)

    def _eli5_summary(self, lines: list[str], constructs: list[str]) -> str:
        if not constructs:
            return "This code does something simple in a few lines."
        mapped = []
        for c in constructs:
            if "function" in c:
                mapped.append("defines a reusable piece of code")
            elif "class" in c:
                mapped.append("creates a blueprint for objects")
            elif "loop" in c:
                mapped.append("repeats something multiple times")
            elif "conditional" in c:
                mapped.append("makes a decision")
            elif "import" in c:
                mapped.append("brings in code from elsewhere")
            elif "error" in c:
                mapped.append("handles things that might go wrong")
            else:
                mapped.append(c)
        return "This code " + ", ".join(mapped) + "."
