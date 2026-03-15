"""Test-to-source mapping — Task 349."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SourceMapping:
    test_file: str
    source_file: str       # inferred source file
    test_functions: tuple[str, ...]
    covered_symbols: tuple[str, ...]   # symbols referenced in tests


@dataclass
class CoverageMap:
    """Maps test files to the source modules they test."""

    mappings: list[SourceMapping] = field(default_factory=list)

    def find_tests_for(self, source_file: str) -> list[SourceMapping]:
        """Return all test mappings that target *source_file*."""
        return [m for m in self.mappings if m.source_file == source_file]

    def find_source_for(self, test_file: str) -> list[SourceMapping]:
        return [m for m in self.mappings if m.test_file == test_file]

    def untested_sources(self, all_sources: set[str]) -> set[str]:
        """Return source files with no corresponding test mapping."""
        tested = {m.source_file for m in self.mappings}
        return all_sources - tested


# Pattern: test_foo.py → foo.py or foo/__init__.py
_TEST_PREFIX_RE = re.compile(r"^test_(.+)$")


def _infer_source(test_file: str) -> str:
    """Infer the source module from a test file name."""
    path = Path(test_file)
    name = path.stem  # e.g. "test_session"
    m = _TEST_PREFIX_RE.match(name)
    if m:
        return m.group(1) + ".py"
    return name + ".py"


def _extract_test_functions(source: str) -> list[str]:
    """Return names of all test_* functions in *source*."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]


def _extract_referenced_names(source: str) -> list[str]:
    """Return all Name.Load identifiers in *source* (potential symbol refs)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return list({
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    })


class TestCoverageMapper:
    """Build a CoverageMap from test file sources."""

    def build(self, test_sources: dict[str, str]) -> CoverageMap:
        """Build mapping from ``{test_file_path: source_code}``."""
        coverage_map = CoverageMap()
        for test_file, source in test_sources.items():
            inferred = _infer_source(Path(test_file).name)
            fns = _extract_test_functions(source)
            symbols = _extract_referenced_names(source)
            mapping = SourceMapping(
                test_file=test_file,
                source_file=inferred,
                test_functions=tuple(fns),
                covered_symbols=tuple(symbols),
            )
            coverage_map.mappings.append(mapping)
        return coverage_map
