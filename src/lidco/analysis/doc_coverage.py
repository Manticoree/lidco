"""Docstring coverage analysis — Task 346."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class DocCoverageResult:
    file: str
    documented_functions: int
    total_functions: int
    documented_classes: int
    total_classes: int

    @property
    def function_coverage(self) -> float:
        if self.total_functions == 0:
            return 1.0
        return self.documented_functions / self.total_functions

    @property
    def class_coverage(self) -> float:
        if self.total_classes == 0:
            return 1.0
        return self.documented_classes / self.total_classes

    @property
    def overall_coverage(self) -> float:
        total = self.total_functions + self.total_classes
        if total == 0:
            return 1.0
        documented = self.documented_functions + self.documented_classes
        return documented / total


def _has_docstring(node: ast.AST) -> bool:
    """Return True if *node* has a docstring as its first statement."""
    body = getattr(node, "body", [])
    if not body:
        return False
    first = body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


class DocCoverageChecker:
    """Measure docstring coverage for functions and classes."""

    def check_source(self, source: str, file_path: str = "") -> DocCoverageResult:
        """Parse *source* and return docstring coverage statistics."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return DocCoverageResult(
                file=file_path,
                documented_functions=0,
                total_functions=0,
                documented_classes=0,
                total_classes=0,
            )

        total_fns = 0
        documented_fns = 0
        total_cls = 0
        documented_cls = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                total_fns += 1
                if _has_docstring(node):
                    documented_fns += 1
            elif isinstance(node, ast.ClassDef):
                total_cls += 1
                if _has_docstring(node):
                    documented_cls += 1

        return DocCoverageResult(
            file=file_path,
            documented_functions=documented_fns,
            total_functions=total_fns,
            documented_classes=documented_cls,
            total_classes=total_cls,
        )
