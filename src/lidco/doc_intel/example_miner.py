"""Find usage examples in code and tests."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CodeExample:
    """A discovered code example."""

    source: str
    file: str
    line: int = 0
    function_name: str = ""
    clarity_score: float = 0.5


class ExampleMiner:
    """Mine code repositories for usage examples of a target name."""

    def __init__(self) -> None:
        self._sources: dict[str, str] = {}

    def find_examples(self, source: str, target_name: str, file: str = "") -> list[CodeExample]:
        """Find all usages of *target_name* in *source*."""
        examples: list[CodeExample] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return examples
        lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body_src = _extract_node_source(lines, node)
                if target_name in body_src and node.name != target_name:
                    score = _score_clarity(body_src, target_name)
                    examples.append(
                        CodeExample(
                            source=body_src,
                            file=file,
                            line=node.lineno,
                            function_name=node.name,
                            clarity_score=score,
                        )
                    )
        return examples

    def rank_by_clarity(self, examples: list[CodeExample]) -> list[CodeExample]:
        """Return examples sorted by clarity_score descending."""
        return sorted(examples, key=lambda e: e.clarity_score, reverse=True)

    def extract_minimal(self, source: str, target_name: str) -> str:
        """Extract the minimal code snippet that uses *target_name*."""
        lines = source.splitlines()
        relevant: list[str] = []
        for line in lines:
            if target_name in line:
                relevant.append(line.strip())
        return "\n".join(relevant) if relevant else ""

    def add_source(self, file: str, source: str) -> None:
        """Register a source file for later searching."""
        self._sources[file] = source

    def search(self, target_name: str) -> list[CodeExample]:
        """Search all registered sources for examples of *target_name*."""
        results: list[CodeExample] = []
        for file, source in self._sources.items():
            results.extend(self.find_examples(source, target_name, file=file))
        return self.rank_by_clarity(results)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _extract_node_source(lines: list[str], node: ast.AST) -> str:
    """Extract source lines for an AST node."""
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", start + 1)
    return "\n".join(lines[start:end])


def _score_clarity(source: str, target_name: str) -> float:
    """Heuristic clarity score (0.0 - 1.0)."""
    score = 0.5
    line_count = source.count("\n") + 1
    # Shorter is clearer
    if line_count <= 5:
        score += 0.2
    elif line_count <= 10:
        score += 0.1
    elif line_count > 30:
        score -= 0.1
    # More usages of target is more illustrative
    usage_count = source.count(target_name)
    if usage_count >= 3:
        score += 0.1
    elif usage_count >= 2:
        score += 0.05
    # Has assert => likely a test, good example
    if "assert" in source.lower():
        score += 0.1
    return max(0.0, min(1.0, score))
