"""Performance hint injection — Task 415."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PerfHint:
    """A performance improvement hint."""

    file: str
    line: int
    kind: str
    message: str
    suggestion: str


class PerformanceAnalyzer:
    """AST-based detection of common performance anti-patterns."""

    def analyze(self, source: str, file_path: str = "") -> list[PerfHint]:
        """Analyze *source* and return a list of PerfHint items."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        hints: list[PerfHint] = []
        self._check_string_concat_in_loop(tree, file_path, hints)
        self._check_len_eq_zero(tree, file_path, hints)
        self._check_sorted_multiple_times(tree, file_path, hints)
        self._check_append_in_loop(tree, file_path, hints)
        self._check_nested_loop_list_ops(tree, file_path, hints)
        return hints

    def analyze_file(self, file_path: str) -> list[PerfHint]:
        """Read *file_path* and analyze it."""
        try:
            source = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            return []
        return self.analyze(source, file_path)

    # ------------------------------------------------------------------ #
    # Checks                                                               #
    # ------------------------------------------------------------------ #

    def _check_string_concat_in_loop(
        self,
        tree: ast.AST,
        file_path: str,
        hints: list[PerfHint],
    ) -> None:
        """Detect `s += "..."` or `s = s + "..."` inside loops."""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.While)):
                continue
            for child in ast.walk(node):
                if child is node:
                    continue
                # AugAssign: s += <str>
                if isinstance(child, ast.AugAssign) and isinstance(child.op, ast.Add):
                    if isinstance(child.value, (ast.Constant, ast.JoinedStr, ast.Name)):
                        hints.append(PerfHint(
                            file=file_path,
                            line=child.lineno,
                            kind="string_concat_in_loop",
                            message="String concatenation with `+=` inside a loop is O(n²)",
                            suggestion="Collect parts in a list and use `''.join(parts)` after the loop",
                        ))

    def _check_len_eq_zero(
        self,
        tree: ast.AST,
        file_path: str,
        hints: list[PerfHint],
    ) -> None:
        """Detect `len(x) == 0` or `len(x) > 0`."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if not isinstance(node.left, ast.Call):
                continue
            func = node.left.func
            if not (isinstance(func, ast.Name) and func.id == "len"):
                continue
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value == 0:
                    op_str = "==" if isinstance(op, ast.Eq) else "!="
                    suggestion = "Use `not x` instead" if isinstance(op, ast.Eq) else "Use `if x:` instead"
                    hints.append(PerfHint(
                        file=file_path,
                        line=node.lineno,
                        kind="len_eq_zero",
                        message=f"`len(x) {op_str} 0` is redundant and slower",
                        suggestion=suggestion,
                    ))

    def _check_sorted_multiple_times(
        self,
        tree: ast.AST,
        file_path: str,
        hints: list[PerfHint],
    ) -> None:
        """Detect `sorted(var)` called more than once on the same variable in a function."""
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            sorted_vars: dict[str, list[int]] = {}
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                func = child.func
                if not (isinstance(func, ast.Name) and func.id == "sorted"):
                    continue
                if not child.args:
                    continue
                first_arg = child.args[0]
                if isinstance(first_arg, ast.Name):
                    sorted_vars.setdefault(first_arg.id, []).append(child.lineno)

            for var_name, lines in sorted_vars.items():
                if len(lines) >= 2:
                    hints.append(PerfHint(
                        file=file_path,
                        line=lines[1],
                        kind="sorted_multiple_times",
                        message=f"`sorted({var_name})` called multiple times — consider caching the result",
                        suggestion=f"Store `sorted_{var_name} = sorted({var_name})` once and reuse it",
                    ))

    def _check_append_in_loop(
        self,
        tree: ast.AST,
        file_path: str,
        hints: list[PerfHint],
    ) -> None:
        """Detect `list.append(...)` inside a for-loop body (possible comprehension)."""
        for node in ast.walk(tree):
            if not isinstance(node, ast.For):
                continue
            for child in ast.walk(node):
                if child is node:
                    continue
                if not isinstance(child, ast.Expr):
                    continue
                call = child.value
                if not isinstance(call, ast.Call):
                    continue
                func = call.func
                if isinstance(func, ast.Attribute) and func.attr == "append":
                    hints.append(PerfHint(
                        file=file_path,
                        line=child.lineno,
                        kind="append_in_loop",
                        message="`list.append()` inside a loop — consider a list comprehension",
                        suggestion="Replace `for x in iterable: lst.append(f(x))` with `lst = [f(x) for x in iterable]`",
                    ))

    def _check_nested_loop_list_ops(
        self,
        tree: ast.AST,
        file_path: str,
        hints: list[PerfHint],
    ) -> None:
        """Detect list subscript access inside nested loops (N+1 pattern)."""
        for outer in ast.walk(tree):
            if not isinstance(outer, (ast.For, ast.While)):
                continue
            for inner in ast.walk(outer):
                if inner is outer:
                    continue
                if not isinstance(inner, (ast.For, ast.While)):
                    continue
                # Check for Subscript access inside inner loop body
                for child in ast.walk(inner):
                    if child is inner:
                        continue
                    if isinstance(child, ast.Subscript) and isinstance(child.ctx, ast.Load):
                        hints.append(PerfHint(
                            file=file_path,
                            line=inner.lineno,
                            kind="nested_loop_list_access",
                            message="List subscript access inside nested loops — potential O(n²) pattern",
                            suggestion="Consider using a dict/set for O(1) lookups or restructure the algorithm",
                        ))
                        break  # one hint per inner loop
                break  # one hint per outer loop
