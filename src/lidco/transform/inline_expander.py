"""AST-based variable inlining — Q134 task 804."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class InlineResult:
    variable_name: str
    value_expr: str
    replacements: int
    new_source: str


class InlineExpander:
    """Replace a variable with its assigned value expression."""

    def inline_variable(self, source: str, variable_name: str) -> InlineResult:
        """Replace *variable_name* with its assigned value everywhere it's read."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return InlineResult(variable_name=variable_name, value_expr="", replacements=0, new_source=source)

        assignments = self.find_assignments(source, variable_name)
        if len(assignments) != 1:
            return InlineResult(variable_name=variable_name, value_expr="", replacements=0, new_source=source)

        assign_line, value_expr = assignments[0]
        lines = source.splitlines(True)

        # Find all Load usages
        usages: list[tuple[int, int]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == variable_name and isinstance(node.ctx, ast.Load):
                usages.append((node.lineno, node.col_offset))

        if not usages:
            return InlineResult(variable_name=variable_name, value_expr=value_expr, replacements=0, new_source=source)

        # Replace usages (reverse order for safe indexing)
        usages.sort(reverse=True)
        for lineno, col in usages:
            idx = lineno - 1
            if 0 <= idx < len(lines):
                line = lines[idx]
                lines[idx] = line[:col] + value_expr + line[col + len(variable_name):]

        # Remove the assignment line
        assign_idx = assign_line - 1
        if 0 <= assign_idx < len(lines):
            lines[assign_idx] = ""

        new_source = "".join(lines)
        return InlineResult(
            variable_name=variable_name,
            value_expr=value_expr,
            replacements=len(usages),
            new_source=new_source,
        )

    def can_inline(self, source: str, variable_name: str) -> bool:
        """Check variable has exactly one simple assignment and no side effects."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return False

        assignments = self.find_assignments(source, variable_name)
        if len(assignments) != 1:
            return False

        # Check the value is a "simple" expression (no calls = no side effects)
        _, value_expr = assignments[0]
        try:
            value_tree = ast.parse(value_expr, mode="eval")
        except SyntaxError:
            return False

        for node in ast.walk(value_tree):
            if isinstance(node, ast.Call):
                return False
        return True

    def find_assignments(self, source: str, variable_name: str) -> List[Tuple[int, str]]:
        """Return (line_number, value_expression) for each assignment to *variable_name*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        lines = source.splitlines()
        results: list[tuple[int, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == variable_name:
                        value_source = ast.get_source_segment(source, node.value)
                        if value_source is None:
                            # Fallback: unparse
                            try:
                                value_source = ast.unparse(node.value)
                            except Exception:
                                value_source = ""
                        results.append((node.lineno, value_source))
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == variable_name and node.value is not None:
                    value_source = ast.get_source_segment(source, node.value)
                    if value_source is None:
                        try:
                            value_source = ast.unparse(node.value)
                        except Exception:
                            value_source = ""
                    results.append((node.lineno, value_source))

        return results
