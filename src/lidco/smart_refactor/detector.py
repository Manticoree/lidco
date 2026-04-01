"""Code smell and refactoring opportunity detection."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class SmellType(str, Enum):
    """Types of code smells."""

    LONG_METHOD = "long_method"
    LARGE_CLASS = "large_class"
    FEATURE_ENVY = "feature_envy"
    DATA_CLUMP = "data_clump"
    DEAD_CODE = "dead_code"
    DEEP_NESTING = "deep_nesting"


@dataclass(frozen=True)
class RefactoringOpportunity:
    """A detected refactoring opportunity."""

    smell: SmellType
    file: str
    name: str
    line: int = 0
    confidence: float = 0.5
    suggestion: str = ""
    estimated_impact: str = "medium"


class RefactoringDetector:
    """Detect code smells and refactoring opportunities in Python source."""

    def __init__(
        self,
        max_method_lines: int = 50,
        max_class_lines: int = 300,
        max_nesting: int = 4,
    ) -> None:
        self.max_method_lines = max_method_lines
        self.max_class_lines = max_class_lines
        self.max_nesting = max_nesting

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_long_methods(
        self, source: str, file: str = ""
    ) -> list[RefactoringOpportunity]:
        """Find methods/functions exceeding *max_method_lines*."""
        opportunities: list[RefactoringOpportunity] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return opportunities

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = node.end_lineno or start
                length = end - start + 1
                if length > self.max_method_lines:
                    confidence = min(1.0, 0.5 + (length - self.max_method_lines) / 100)
                    impact = (
                        "high"
                        if length > self.max_method_lines * 2
                        else "medium"
                    )
                    opportunities.append(
                        RefactoringOpportunity(
                            smell=SmellType.LONG_METHOD,
                            file=file,
                            name=node.name,
                            line=start,
                            confidence=round(confidence, 2),
                            suggestion=f"Method '{node.name}' is {length} lines (limit {self.max_method_lines}). Consider extracting helpers.",
                            estimated_impact=impact,
                        )
                    )
        return opportunities

    def detect_deep_nesting(
        self, source: str, file: str = ""
    ) -> list[RefactoringOpportunity]:
        """Find deeply nested blocks exceeding *max_nesting*."""
        opportunities: list[RefactoringOpportunity] = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return opportunities

        nesting_nodes = (
            ast.If,
            ast.For,
            ast.While,
            ast.With,
            ast.Try,
            ast.AsyncFor,
            ast.AsyncWith,
        )

        def _walk(node: ast.AST, depth: int, func_name: str) -> None:
            for child in ast.iter_child_nodes(node):
                new_depth = depth
                name = func_name
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = child.name
                    new_depth = 0
                if isinstance(child, nesting_nodes):
                    new_depth = depth + 1
                    if new_depth > self.max_nesting:
                        opportunities.append(
                            RefactoringOpportunity(
                                smell=SmellType.DEEP_NESTING,
                                file=file,
                                name=name or "<module>",
                                line=child.lineno,
                                confidence=min(1.0, 0.6 + new_depth * 0.05),
                                suggestion=f"Nesting depth {new_depth} exceeds limit {self.max_nesting}. Consider early returns or extraction.",
                                estimated_impact="medium",
                            )
                        )
                _walk(child, new_depth, name)

        _walk(tree, 0, "")
        return opportunities

    def detect_all(
        self, source: str, file: str = ""
    ) -> list[RefactoringOpportunity]:
        """Run all detectors and return combined results."""
        results: list[RefactoringOpportunity] = []
        results.extend(self.detect_long_methods(source, file))
        results.extend(self.detect_deep_nesting(source, file))
        return results

    def configure(
        self,
        max_method_lines: int | None = None,
        max_nesting: int | None = None,
    ) -> None:
        """Update detector thresholds."""
        if max_method_lines is not None:
            self.max_method_lines = max_method_lines
        if max_nesting is not None:
            self.max_nesting = max_nesting

    def summary(self, opportunities: list[RefactoringOpportunity]) -> str:
        """Return a human-readable summary of opportunities."""
        if not opportunities:
            return "No refactoring opportunities detected."
        counts: dict[str, int] = {}
        for opp in opportunities:
            counts[opp.smell.value] = counts.get(opp.smell.value, 0) + 1
        lines = [f"Found {len(opportunities)} refactoring opportunity(ies):"]
        for smell, count in sorted(counts.items()):
            lines.append(f"  - {smell}: {count}")
        return "\n".join(lines)
