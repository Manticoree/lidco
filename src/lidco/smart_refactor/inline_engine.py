"""Inline variable/method/constant."""
from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass
from enum import Enum


class InlineType(str, Enum):
    """Kind of inline operation."""

    VARIABLE = "variable"
    METHOD = "method"
    CONSTANT = "constant"


@dataclass(frozen=True)
class InlineResult:
    """Result of an inline operation."""

    type: InlineType
    name: str
    occurrences: int = 0
    result_code: str = ""
    success: bool = True
    error: str = ""


class InlineEngine:
    """Inline variables, constants, and simple methods."""

    def __init__(self) -> None:
        pass

    def inline_variable(self, source: str, var_name: str) -> InlineResult:
        """Replace a variable with its assigned value and remove the assignment."""
        # Find assignment: ``var_name = <expr>``
        pattern = re.compile(
            r"^(\s*)" + re.escape(var_name) + r"\s*=\s*(.+)$", re.MULTILINE
        )
        m = pattern.search(source)
        if not m:
            return InlineResult(
                type=InlineType.VARIABLE,
                name=var_name,
                success=False,
                error=f"No assignment found for '{var_name}'.",
            )

        value = m.group(2).strip()
        # Remove the assignment line
        without_assign = source[: m.start()] + source[m.end() :]
        # Strip leading newline left behind
        if without_assign.startswith("\n"):
            without_assign = without_assign[1:]

        # Replace remaining whole-word occurrences
        ref_pattern = re.compile(r"\b" + re.escape(var_name) + r"\b")
        occurrences = len(ref_pattern.findall(without_assign))
        result_code = ref_pattern.sub(value, without_assign)

        return InlineResult(
            type=InlineType.VARIABLE,
            name=var_name,
            occurrences=occurrences,
            result_code=result_code,
            success=True,
        )

    def inline_constant(
        self, source: str, const_name: str, value: str
    ) -> InlineResult:
        """Replace all uses of *const_name* with *value* and remove definition."""
        pattern = re.compile(
            r"^(\s*)" + re.escape(const_name) + r"\s*=\s*.+$", re.MULTILINE
        )
        m = pattern.search(source)
        if not m:
            return InlineResult(
                type=InlineType.CONSTANT,
                name=const_name,
                success=False,
                error=f"No definition found for '{const_name}'.",
            )

        without_def = source[: m.start()] + source[m.end() :]
        if without_def.startswith("\n"):
            without_def = without_def[1:]

        ref_pattern = re.compile(r"\b" + re.escape(const_name) + r"\b")
        occurrences = len(ref_pattern.findall(without_def))
        result_code = ref_pattern.sub(value, without_def)

        return InlineResult(
            type=InlineType.CONSTANT,
            name=const_name,
            occurrences=occurrences,
            result_code=result_code,
            success=True,
        )

    def detect_inlinable(self, source: str) -> list[str]:
        """Find variable names that are assigned once and used only once."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        # Count assignments and usages
        assignments: dict[str, int] = {}
        usages: dict[str, int] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments[target.id] = assignments.get(target.id, 0) + 1
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                usages[node.id] = usages.get(node.id, 0) + 1

        result: list[str] = []
        for name, assign_count in sorted(assignments.items()):
            if assign_count == 1 and usages.get(name, 0) == 1:
                result.append(name)
        return result

    def preview(self, result: InlineResult) -> str:
        """Return a text preview of the inline result."""
        if not result.success:
            return f"Error: {result.error}"
        return (
            f"Inlined '{result.name}' ({result.occurrences} occurrence(s)).\n"
            f"Result:\n{result.result_code}"
        )
