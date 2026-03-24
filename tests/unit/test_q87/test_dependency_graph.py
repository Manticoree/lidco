"""Tests for DependencyGraph (T567)."""
from __future__ import annotations
import textwrap
from pathlib import Path
import pytest
from lidco.graph.dependency_graph import DependencyGraph, Edge


SOURCE_A = textwrap.dedent("""\
    import os
    from pathlib import Path

    class Foo(Base):
        pass

    def bar():
        baz()
""")


def test_imports_detected():
    g = DependencyGraph()
    g.build_from_source(SOURCE_A, module_name="mod_a")
    edges = g.edges_from("mod_a", kind="imports")
    dsts = {e.dst for e in edges}
    assert "os" in dsts
    assert "pathlib" in dsts


def test_inherits_detected():
    g = DependencyGraph()
    g.build_from_source(SOURCE_A, module_name="mod_a")
    edges = g.edges_from("Foo", kind="inherits")
    assert any(e.dst == "Base" for e in edges)


def test_calls_detected():
    g = DependencyGraph()
    g.build_from_source(SOURCE_A)
    call_edges = [e for e in g._edges if e.kind == "calls"]
    assert any(e.dst == "baz" for e in call_edges)


def test_reachable_bfs():
    g = DependencyGraph()
    g.add_edge(Edge(src="a", dst="b", kind="imports", file="", line=1))
    g.add_edge(Edge(src="b", dst="c", kind="imports", file="", line=1))
    reached = g.reachable("a", max_depth=5)
    assert "b" in reached
    assert "c" in reached


def test_dependents():
    g = DependencyGraph()
    g.add_edge(Edge(src="x", dst="lib", kind="imports", file="", line=1))
    g.add_edge(Edge(src="y", dst="lib", kind="imports", file="", line=1))
    deps = g.dependents("lib")
    assert "x" in deps and "y" in deps


def test_build_from_directory(tmp_path):
    (tmp_path / "mod.py").write_text("import os\ndef foo(): pass\n")
    g = DependencyGraph()
    g.build_from_directory(tmp_path)
    assert len(g._edges) > 0


def test_stats():
    g = DependencyGraph()
    g.build_from_source(SOURCE_A, module_name="m")
    stats = g.stats()
    assert stats.edges > 0
    assert stats.nodes > 0


def test_format_stats():
    g = DependencyGraph()
    g.build_from_source(SOURCE_A, module_name="m")
    s = g.format_stats()
    assert "Dependency Graph" in s


def test_syntax_error_handled():
    g = DependencyGraph()
    g.build_from_source("def (broken syntax!!!", module_name="bad")
    # Should not raise
    assert len(g._edges) == 0
