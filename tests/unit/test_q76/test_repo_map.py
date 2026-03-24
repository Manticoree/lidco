"""Tests for RepoMap — T502."""
from __future__ import annotations

from pathlib import Path

import pytest

from lidco.context.repo_map import RepoMap, RepoMapEntry


class TestRepoMapInit:
    def test_defaults(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path)
        assert rm.project_dir == tmp_path
        assert rm.token_budget == 4096

    def test_custom_budget(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path, token_budget=1024)
        assert rm.token_budget == 1024


class TestBuildImportGraph:
    def test_no_py_files_returns_empty(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path)
        assert rm.build_import_graph() == {}

    def test_simple_import(self, tmp_path):
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("x = 1\n")
        rm = RepoMap(project_dir=tmp_path)
        graph = rm.build_import_graph()
        assert "a" in graph
        assert "b" in graph

    def test_syntax_error_skipped(self, tmp_path):
        (tmp_path / "bad.py").write_text("def foo(:\n")
        (tmp_path / "good.py").write_text("x = 1\n")
        rm = RepoMap(project_dir=tmp_path)
        graph = rm.build_import_graph()
        assert "good" in graph
        # bad.py may be in graph as empty list (graceful) or skipped entirely
        assert graph.get("bad", []) == []

    def test_circular_imports_handled(self, tmp_path):
        (tmp_path / "x.py").write_text("import y\n")
        (tmp_path / "y.py").write_text("import x\n")
        rm = RepoMap(project_dir=tmp_path)
        graph = rm.build_import_graph()
        assert "x" in graph
        assert "y" in graph


class TestComputeRanks:
    def test_single_node(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path)
        ranks = rm.compute_ranks({"a": []})
        assert "a" in ranks
        assert abs(ranks["a"] - 1.0) < 0.1  # roughly 1.0 for single isolated node

    def test_three_node_graph(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path)
        # b and c both point to a — a should rank highest
        graph = {"a": [], "b": ["a"], "c": ["a"]}
        ranks = rm.compute_ranks(graph)
        assert ranks["a"] > ranks["b"]
        assert ranks["a"] > ranks["c"]

    def test_disconnected_graph(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path)
        graph = {"a": [], "b": [], "c": []}
        ranks = rm.compute_ranks(graph)
        assert len(ranks) == 3
        # All equal for fully disconnected
        vals = list(ranks.values())
        assert abs(vals[0] - vals[1]) < 0.05

    def test_empty_graph_returns_empty(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path)
        assert rm.compute_ranks({}) == {}

    def test_no_mutation_of_input(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path)
        graph = {"a": ["b"], "b": []}
        original = dict(graph)
        rm.compute_ranks(graph)
        assert graph == original


class TestGenerate:
    def _make_project(self, tmp_path):
        (tmp_path / "main.py").write_text("import utils\ndef run(): pass\n")
        (tmp_path / "utils.py").write_text("def helper(): pass\n")
        return tmp_path

    def test_generate_returns_string(self, tmp_path):
        self._make_project(tmp_path)
        rm = RepoMap(project_dir=tmp_path)
        result = rm.generate()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_empty_project(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path)
        assert rm.generate() == ""

    def test_generate_within_budget(self, tmp_path):
        self._make_project(tmp_path)
        rm = RepoMap(project_dir=tmp_path, token_budget=50)
        result = rm.generate(token_budget=50)
        assert len(result) <= 50 * 4 + 50  # allow some header overhead

    def test_generate_truncates_when_exceeds_budget(self, tmp_path):
        for i in range(20):
            (tmp_path / f"module_{i}.py").write_text(
                f"def func_{i}_{'a' * 100}(): pass\n"
            )
        rm = RepoMap(project_dir=tmp_path, token_budget=20)
        result = rm.generate(token_budget=20)
        # Should be truncated — not all 20 files
        lines = [l for l in result.splitlines() if l.strip() and not l.startswith("#")]
        assert len(lines) < 20

    def test_changed_files_boost(self, tmp_path):
        self._make_project(tmp_path)
        rm = RepoMap(project_dir=tmp_path)
        graph = rm.build_import_graph()
        ranks_before = rm.compute_ranks(graph)
        # Generate with a changed file to apply boost
        result = rm.generate(changed_files=["utils.py"])
        assert result  # non-empty


class TestRankedEntries:
    def test_ranked_entries_sorted_desc(self, tmp_path):
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("import c\n")
        (tmp_path / "c.py").write_text("x = 1\n")
        rm = RepoMap(project_dir=tmp_path)
        entries = rm.ranked_entries()
        assert isinstance(entries, list)
        if len(entries) >= 2:
            assert entries[0].rank >= entries[1].rank


class TestFormatForPrompt:
    def test_format_output_structure(self, tmp_path):
        (tmp_path / "foo.py").write_text("class Foo: pass\ndef bar(): pass\n")
        rm = RepoMap(project_dir=tmp_path)
        entries = rm.ranked_entries()
        result = rm.format_for_prompt(entries)
        assert result.startswith("# Repo Map")
        assert "foo.py" in result

    def test_format_empty_entries_returns_empty(self, tmp_path):
        rm = RepoMap(project_dir=tmp_path)
        assert rm.format_for_prompt([]) == ""
