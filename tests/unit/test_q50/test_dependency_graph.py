"""Tests for DependencyGraph and DependencyGraphBuilder — Task 343."""

from __future__ import annotations

import pytest

from lidco.analysis.dependency_graph import DependencyGraph, DependencyGraphBuilder


class TestDependencyGraph:
    def test_add_edge(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        assert "b" in g.dependencies_of("a")

    def test_all_modules(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        modules = g.all_modules()
        assert {"a", "b", "c"} == modules

    def test_dependencies_of_missing(self):
        g = DependencyGraph()
        assert g.dependencies_of("nonexistent") == set()

    def test_transitive_deps(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "d")
        deps = g.transitive_deps("a")
        assert deps == {"b", "c", "d"}

    def test_transitive_deps_no_deps(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        assert g.transitive_deps("b") == set()

    def test_transitive_deps_cycle_safe(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")  # cycle
        # Should not hang
        deps = g.transitive_deps("a")
        assert "b" in deps

    def test_find_cycles_simple(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        cycles = g.find_cycles()
        assert len(cycles) >= 1

    def test_find_cycles_none(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        cycles = g.find_cycles()
        assert cycles == []

    def test_reverse(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        rev = g.reverse()
        assert "a" in rev.dependencies_of("b")
        assert "b" not in rev.dependencies_of("a")


class TestDependencyGraphBuilder:
    def setup_method(self):
        self.builder = DependencyGraphBuilder()

    def test_empty_sources(self):
        graph = self.builder.build({})
        assert graph.all_modules() == set()

    def test_single_file_no_imports(self):
        graph = self.builder.build({"mymod": "x = 1\n"})
        # mymod has no dependencies
        assert graph.dependencies_of("mymod") == set()

    def test_internal_dependency(self):
        sources = {
            "mymod": "import utils\n",
            "utils": "def helper(): pass\n",
        }
        graph = self.builder.build(sources)
        assert "utils" in graph.dependencies_of("mymod")

    def test_external_dependency_ignored(self):
        sources = {"mymod": "import os\nimport sys\n"}
        graph = self.builder.build(sources)
        # os/sys are not in known modules
        assert graph.dependencies_of("mymod") == set()

    def test_from_import(self):
        sources = {
            "mymod": "from utils import helper\n",
            "utils": "def helper(): pass\n",
        }
        graph = self.builder.build(sources)
        assert "utils" in graph.dependencies_of("mymod")

    def test_syntax_error_file_skipped(self):
        sources = {
            "good": "import bad\n",
            "bad": "def broken(:\n",
        }
        # Should not raise
        graph = self.builder.build(sources)
        assert isinstance(graph, DependencyGraph)

    def test_build_from_files_path_to_module_name(self):
        # Verify _path_to_module converts paths correctly
        assert self.builder._path_to_module("src/foo/bar.py") == "foo.bar"
        assert self.builder._path_to_module("src/utils.py") == "utils"
        assert self.builder._path_to_module("lib/helper.py") == "helper"
