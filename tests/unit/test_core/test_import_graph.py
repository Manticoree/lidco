"""Tests for import_graph — AST-based import dependency graph with cycle detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from lidco.core.import_graph import (
    ImportEdge,
    ImportGraph,
    _find_cycles,
    _module_from_path,
    _parse_imports,
    build_graph,
)


# ---------------------------------------------------------------------------
# _module_from_path
# ---------------------------------------------------------------------------


class TestModuleFromPath:
    def test_src_prefix_stripped(self, tmp_path):
        path = tmp_path / "src" / "lidco" / "core" / "session.py"
        path.parent.mkdir(parents=True)
        path.touch()
        assert _module_from_path(path, tmp_path) == "lidco.core.session"

    def test_init_becomes_package(self, tmp_path):
        path = tmp_path / "src" / "lidco" / "core" / "__init__.py"
        path.parent.mkdir(parents=True)
        path.touch()
        assert _module_from_path(path, tmp_path) == "lidco.core"

    def test_no_src_prefix(self, tmp_path):
        path = tmp_path / "pkg" / "utils.py"
        path.parent.mkdir(parents=True)
        path.touch()
        assert _module_from_path(path, tmp_path) == "pkg.utils"

    def test_top_level_file(self, tmp_path):
        path = tmp_path / "conftest.py"
        path.touch()
        assert _module_from_path(path, tmp_path) == "conftest"

    def test_root_init(self, tmp_path):
        path = tmp_path / "src" / "mypkg" / "__init__.py"
        path.parent.mkdir(parents=True)
        path.touch()
        assert _module_from_path(path, tmp_path) == "mypkg"


# ---------------------------------------------------------------------------
# _parse_imports
# ---------------------------------------------------------------------------


class TestParseImports:
    def test_simple_import(self):
        source = "import os\nimport sys\n"
        edges = _parse_imports(source, "test.py", "")
        assert len(edges) == 2
        modules = {e.module for e in edges}
        assert "os" in modules
        assert "sys" in modules
        for e in edges:
            assert e.names == ()
            assert e.is_relative is False

    def test_from_import_single_name(self):
        source = "from pathlib import Path\n"
        edges = _parse_imports(source, "test.py", "")
        assert len(edges) == 1
        assert edges[0].module == "pathlib"
        assert edges[0].names == ("Path",)
        assert edges[0].is_relative is False

    def test_from_import_multiple_names(self):
        source = "from os.path import join, exists\n"
        edges = _parse_imports(source, "test.py", "")
        assert len(edges) == 1
        assert edges[0].module == "os.path"
        assert set(edges[0].names) == {"join", "exists"}

    def test_star_import(self):
        source = "from typing import *\n"
        edges = _parse_imports(source, "test.py", "")
        assert len(edges) == 1
        assert edges[0].names == ("*",)

    def test_relative_import_submodule(self):
        # from .utils import func — in package lidco.core
        source = "from .utils import func\n"
        edges = _parse_imports(source, "lidco/core/session.py", "lidco.core.session")
        assert len(edges) == 1
        assert edges[0].is_relative is True
        assert edges[0].module == "lidco.core.utils"
        assert edges[0].names == ("func",)

    def test_relative_import_from_package(self):
        # from . import config — in package lidco.core
        source = "from . import config\n"
        edges = _parse_imports(source, "lidco/core/session.py", "lidco.core.session")
        assert len(edges) == 1
        assert edges[0].is_relative is True
        assert edges[0].module == "lidco.core.config"

    def test_relative_import_from_init_file(self):
        # from .a import X inside pkg/__init__.py (pkg_name = "pkg")
        # Level 1 in __init__.py means "same package" → should resolve to pkg.a
        source = "from .a import SomeClass\n"
        edges = _parse_imports(source, "pkg/__init__.py", "pkg")
        assert len(edges) == 1
        assert edges[0].is_relative is True
        assert edges[0].module == "pkg.a"

    def test_relative_import_multiple_names(self):
        # from . import config, errors — each becomes its own edge
        source = "from . import config, errors\n"
        edges = _parse_imports(source, "lidco/core/session.py", "lidco.core.session")
        assert len(edges) == 2
        modules = {e.module for e in edges}
        assert "lidco.core.config" in modules
        assert "lidco.core.errors" in modules

    def test_syntax_error_returns_empty(self):
        source = "def broken(\n"
        edges = _parse_imports(source, "test.py", "")
        assert edges == []

    def test_empty_file(self):
        edges = _parse_imports("", "test.py", "")
        assert edges == []

    def test_line_number_captured(self):
        source = "# comment\nimport os\n"
        edges = _parse_imports(source, "test.py", "")
        assert len(edges) == 1
        assert edges[0].line == 2


# ---------------------------------------------------------------------------
# _find_cycles
# ---------------------------------------------------------------------------


class TestFindCycles:
    def test_no_cycles_empty(self):
        assert _find_cycles({}) == []

    def test_no_cycles_linear(self):
        adjacency = {"a": ["b"], "b": ["c"], "c": []}
        assert _find_cycles(adjacency) == []

    def test_direct_cycle(self):
        adjacency = {"a": ["b"], "b": ["a"]}
        cycles = _find_cycles(adjacency)
        assert len(cycles) == 1
        assert frozenset(cycles[0]) == frozenset({"a", "b"})

    def test_self_loop(self):
        adjacency = {"a": ["a"]}
        cycles = _find_cycles(adjacency)
        assert len(cycles) == 1
        assert "a" in cycles[0]

    def test_transitive_cycle(self):
        # A → B → C → A
        adjacency = {"a": ["b"], "b": ["c"], "c": ["a"]}
        cycles = _find_cycles(adjacency)
        assert len(cycles) == 1
        assert frozenset(cycles[0]) == frozenset({"a", "b", "c"})

    def test_deduplication(self):
        # A ↔ B creates only ONE cycle, not two (A→B→A and B→A→B)
        adjacency = {"a": ["b"], "b": ["a"]}
        cycles = _find_cycles(adjacency)
        assert len(cycles) == 1

    def test_no_cycle_with_shared_node(self):
        # A → C, B → C — diamond, no cycle
        adjacency = {"a": ["c"], "b": ["c"], "c": []}
        assert _find_cycles(adjacency) == []


# ---------------------------------------------------------------------------
# build_graph — integration with tmp_path
# ---------------------------------------------------------------------------


class TestBuildGraph:
    def test_empty_directory(self, tmp_path):
        graph = build_graph(tmp_path)
        assert graph.edges == []
        assert graph.get_files() == []

    def test_single_file_external_import(self, tmp_path):
        (tmp_path / "main.py").write_text("import os\nimport sys\n")
        graph = build_graph(tmp_path)
        assert len(graph.edges) == 2
        assert any(e.module == "os" for e in graph.edges)
        assert any(e.module == "sys" for e in graph.edges)

    def test_two_files_no_cycle(self, tmp_path):
        (tmp_path / "a.py").write_text("import os\n")
        (tmp_path / "b.py").write_text("import sys\n")
        graph = build_graph(tmp_path)
        assert len(graph.find_cycles()) == 0

    def test_cycle_via_relative_imports(self, tmp_path):
        # Create package pkg with a.py and b.py that import each other
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("from . import b\n")
        (pkg / "b.py").write_text("from . import a\n")
        graph = build_graph(tmp_path)
        cycles = graph.find_cycles()
        assert len(cycles) >= 1
        # Cycle must involve pkg.a and pkg.b
        cycle_modules = frozenset(m for c in cycles for m in c)
        assert "pkg.a" in cycle_modules
        assert "pkg.b" in cycle_modules

    def test_no_cycle_with_only_external_imports(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "a.py").write_text("import os\nfrom pathlib import Path\n")
        (pkg / "b.py").write_text("import sys\n")
        graph = build_graph(tmp_path)
        assert graph.find_cycles() == []

    def test_syntax_error_file_skipped(self, tmp_path):
        (tmp_path / "good.py").write_text("import os\n")
        (tmp_path / "bad.py").write_text("def broken(\n")
        # Should not raise
        graph = build_graph(tmp_path)
        assert any(e.module == "os" for e in graph.edges)


# ---------------------------------------------------------------------------
# ImportGraph.summary()
# ---------------------------------------------------------------------------


class TestImportGraphSummary:
    def test_summary_no_cycles(self, tmp_path):
        (tmp_path / "a.py").write_text("import os\n")
        graph = build_graph(tmp_path)
        summary = graph.summary()
        assert "No circular imports" in summary
        assert "[OK]" in summary

    def test_summary_with_cycles(self, tmp_path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "x.py").write_text("from . import y\n")
        (pkg / "y.py").write_text("from . import x\n")
        graph = build_graph(tmp_path)
        cycles = graph.find_cycles()
        # The setup guarantees a cycle — detection must not be empty
        assert len(cycles) >= 1
        summary = graph.summary()
        assert "WARNING" in summary or "circular" in summary.lower()

    def test_summary_counts_files(self, tmp_path):
        (tmp_path / "a.py").write_text("import os\n")
        (tmp_path / "b.py").write_text("import sys\n")
        graph = build_graph(tmp_path)
        summary = graph.summary()
        assert "2" in summary  # 2 files scanned
