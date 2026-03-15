"""Cyclomatic and cognitive complexity analysis — Task 337."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class FunctionComplexity:
    name: str
    file: str
    line: int
    cyclomatic: int
    cognitive: int


class ComplexityAnalyzer:
    """Compute cyclomatic and cognitive complexity per function via AST."""

    def analyze_source(
        self, source: str, file_path: str = ""
    ) -> list[FunctionComplexity]:
        """Parse *source* and return complexity for every function/method."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        results: list[FunctionComplexity] = []
        self._walk_tree(tree, file_path, results)
        return results

    def score_risk(self, fc: FunctionComplexity) -> str:
        """Return "low", "medium", or "high" based on cyclomatic complexity."""
        if fc.cyclomatic < 5:
            return "low"
        if fc.cyclomatic < 10:
            return "medium"
        return "high"

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _walk_tree(
        self,
        tree: ast.AST,
        file_path: str,
        results: list[FunctionComplexity],
    ) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cyclomatic = self._cyclomatic(node)
                cognitive = self._cognitive(node, depth=0)
                results.append(
                    FunctionComplexity(
                        name=node.name,
                        file=file_path,
                        line=node.lineno,
                        cyclomatic=cyclomatic,
                        cognitive=cognitive,
                    )
                )

    def _cyclomatic(self, func_node: ast.AST) -> int:
        """Count branching nodes; start at 1."""
        count = 1
        for node in ast.walk(func_node):
            if isinstance(node, (ast.If, ast.IfExp)):
                count += 1
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                count += 1
            elif isinstance(node, (ast.While,)):
                count += 1
            elif isinstance(node, ast.ExceptHandler):
                count += 1
            elif isinstance(node, ast.With):
                count += 1
            elif isinstance(node, ast.Assert):
                count += 1
            elif isinstance(node, ast.BoolOp):
                # each `and`/`or` operator is one branch per extra value
                count += len(node.values) - 1
        return count

    def _cognitive(self, node: ast.AST, depth: int) -> int:
        """Compute cognitive complexity with nesting bonus."""
        score = 0
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.IfExp, ast.For, ast.AsyncFor,
                                   ast.While, ast.ExceptHandler, ast.With,
                                   ast.AsyncWith)):
                score += 1 + depth
                score += self._cognitive(child, depth + 1)
            elif isinstance(child, ast.BoolOp):
                score += len(child.values) - 1
                score += self._cognitive(child, depth)
            else:
                score += self._cognitive(child, depth)
        return score
