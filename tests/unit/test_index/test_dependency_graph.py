"""Tests for DependencyGraph and IndexContextEnricher.get_related_files()."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from lidco.index.context_enricher import IndexContextEnricher
from lidco.index.db import IndexDatabase
from lidco.index.dependency_graph import DependencyGraph, _min_rotation
from lidco.index.schema import FileRecord, ImportRecord


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path: Path) -> IndexDatabase:
    return IndexDatabase(tmp_path / ".lidco" / "index.db")


def _insert_file(db: IndexDatabase, path: str, role: str = "utility") -> int:
    rec = FileRecord(
        path=path,
        language="python",
        role=role,
        size_bytes=100,
        mtime=time.time(),
        lines_count=10,
        indexed_at=time.time(),
    )
    return db.upsert_file(rec)


def _insert_import(
    db: IndexDatabase,
    from_file_id: int,
    resolved_path: str,
    module: str = "module",
) -> None:
    db.insert_imports([
        ImportRecord(
            from_file_id=from_file_id,
            imported_module=module,
            resolved_path=resolved_path,
            import_kind="from",
        )
    ])


# ── DependencyGraph tests ──────────────────────────────────────────────────────

class TestDependencyGraph:
    def test_empty_db_no_relations(self, db: IndexDatabase):
        graph = DependencyGraph(db)
        assert graph.get_dependencies("src/foo.py") == []
        assert graph.get_dependents("src/foo.py") == []

    def test_get_dependencies_direct(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        b_id = _insert_file(db, "src/b.py")
        _insert_import(db, a_id, "src/b.py")  # a imports b

        graph = DependencyGraph(db)
        deps = graph.get_dependencies("src/a.py")
        assert len(deps) == 1
        assert deps[0].path == "src/b.py"

    def test_get_dependents_direct(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        _insert_file(db, "src/b.py")
        b_id = _insert_file(db, "src/b.py")
        c_id = _insert_file(db, "src/c.py")
        _insert_import(db, b_id, "src/a.py")  # b imports a
        _insert_import(db, c_id, "src/a.py")  # c imports a

        graph = DependencyGraph(db)
        dependents = graph.get_dependents("src/a.py")
        paths = {r.path for r in dependents}
        assert "src/b.py" in paths
        assert "src/c.py" in paths

    def test_self_import_ignored(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        _insert_import(db, a_id, "src/a.py")  # should be filtered out

        graph = DependencyGraph(db)
        assert graph.get_dependencies("src/a.py") == []
        assert graph.get_dependents("src/a.py") == []

    def test_get_related_prioritises_dependents(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        b_id = _insert_file(db, "src/b.py")  # imports a (dependent of a)
        c_id = _insert_file(db, "src/c.py")  # imported by a (dependency of a)
        _insert_import(db, b_id, "src/a.py")  # b → a
        _insert_import(db, a_id, "src/c.py")  # a → c

        graph = DependencyGraph(db)
        related = graph.get_related("src/a.py")

        # b (dependent) should come before c (dependency)
        paths = [r.record.path for r in related]
        assert "src/b.py" in paths
        assert "src/c.py" in paths
        assert paths.index("src/b.py") < paths.index("src/c.py")

    def test_get_related_relation_labels(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        b_id = _insert_file(db, "src/b.py")
        c_id = _insert_file(db, "src/c.py")
        _insert_import(db, b_id, "src/a.py")  # b imports a → b is imported_by relation for a
        _insert_import(db, a_id, "src/c.py")  # a imports c → c is imports relation for a

        graph = DependencyGraph(db)
        related = graph.get_related("src/a.py")
        by_path = {r.record.path: r for r in related}

        assert by_path["src/b.py"].relation == "imported_by"
        assert by_path["src/c.py"].relation == "imports"

    def test_get_related_respects_limit(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        for i in range(10):
            dep_id = _insert_file(db, f"src/dep{i}.py")
            _insert_import(db, dep_id, "src/a.py")

        graph = DependencyGraph(db)
        related = graph.get_related("src/a.py", limit=3)
        assert len(related) == 3

    def test_no_duplicates_in_related(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        b_id = _insert_file(db, "src/b.py")
        # b imports a AND a imports b (circular — unusual but valid)
        _insert_import(db, b_id, "src/a.py")
        _insert_import(db, a_id, "src/b.py")

        graph = DependencyGraph(db)
        related = graph.get_related("src/a.py")
        paths = [r.record.path for r in related]
        assert len(paths) == len(set(paths))  # no duplicates

    def test_unresolved_import_skipped(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        # Import with empty resolved_path should be silently skipped
        db.insert_imports([ImportRecord(
            from_file_id=a_id,
            imported_module="os",
            resolved_path="",  # standard library, not resolved
        )])

        graph = DependencyGraph(db)
        assert graph.get_dependencies("src/a.py") == []


# ── IndexContextEnricher integration ──────────────────────────────────────────

class TestContextEnricherRelatedFiles:
    def test_get_related_files_empty_index(self, db: IndexDatabase):
        enricher = IndexContextEnricher(db)
        result = enricher.get_related_files("src/a.py")
        assert result == ""

    def test_get_related_files_no_imports(self, db: IndexDatabase):
        _insert_file(db, "src/a.py")
        enricher = IndexContextEnricher(db)
        result = enricher.get_related_files("src/a.py")
        assert result == ""

    def test_get_related_files_returns_section(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        b_id = _insert_file(db, "src/b.py")
        _insert_import(db, b_id, "src/a.py")  # b imports a

        enricher = IndexContextEnricher(db)
        result = enricher.get_related_files("src/a.py")
        assert "## Related files" in result
        assert "src/b.py" in result

    def test_get_context_with_current_file(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        b_id = _insert_file(db, "src/b.py")
        _insert_import(db, b_id, "src/a.py")

        enricher = IndexContextEnricher(db)
        ctx = enricher.get_context(current_file="src/a.py")
        assert "## Related files" in ctx
        assert "src/b.py" in ctx

    def test_get_context_without_current_file_has_no_related(self, db: IndexDatabase):
        a_id = _insert_file(db, "src/a.py")
        b_id = _insert_file(db, "src/b.py")
        _insert_import(db, b_id, "src/a.py")

        enricher = IndexContextEnricher(db)
        ctx = enricher.get_context()  # no current_file
        assert "## Related files" not in ctx


# ── DependencyGraph.find_cycles ───────────────────────────────────────────────

class TestMinRotation:
    def test_single_element(self):
        assert _min_rotation(["a"]) == ("a",)

    def test_already_minimal(self):
        assert _min_rotation(["a", "b", "c"]) == ("a", "b", "c")

    def test_rotation_applied(self):
        # ["c", "a", "b"] rotated → min is ("a", "b", "c")
        assert _min_rotation(["c", "a", "b"]) == ("a", "b", "c")


class TestFindCycles:
    def test_no_cycles_acyclic_graph(self, db: IndexDatabase):
        a_id = _insert_file(db, "a.py")
        b_id = _insert_file(db, "b.py")
        _insert_import(db, a_id, "b.py")  # a → b (no cycle)
        graph = DependencyGraph(db)
        assert graph.find_cycles() == []

    def test_simple_two_node_cycle(self, db: IndexDatabase):
        a_id = _insert_file(db, "a.py")
        b_id = _insert_file(db, "b.py")
        _insert_import(db, a_id, "b.py")  # a → b
        _insert_import(db, b_id, "a.py")  # b → a  ← cycle
        graph = DependencyGraph(db)
        cycles = graph.find_cycles()
        assert len(cycles) == 1
        assert set(cycles[0]) == {"a.py", "b.py"}

    def test_three_node_cycle(self, db: IndexDatabase):
        a_id = _insert_file(db, "a.py")
        b_id = _insert_file(db, "b.py")
        c_id = _insert_file(db, "c.py")
        _insert_import(db, a_id, "b.py")  # a → b
        _insert_import(db, b_id, "c.py")  # b → c
        _insert_import(db, c_id, "a.py")  # c → a  ← cycle
        graph = DependencyGraph(db)
        cycles = graph.find_cycles()
        assert len(cycles) == 1
        assert set(cycles[0]) == {"a.py", "b.py", "c.py"}

    def test_self_import_not_tracked(self, db: IndexDatabase):
        """Self-imports are filtered out during graph construction — not a cycle."""
        a_id = _insert_file(db, "a.py")
        _insert_import(db, a_id, "a.py")  # a → a (self-import, filtered)
        graph = DependencyGraph(db)
        # Self-loops are stripped in _ensure_built(); find_cycles sees no edges
        assert graph.find_cycles() == []

    def test_two_independent_cycles(self, db: IndexDatabase):
        # Cycle 1: a ↔ b
        a_id = _insert_file(db, "a.py")
        b_id = _insert_file(db, "b.py")
        _insert_import(db, a_id, "b.py")
        _insert_import(db, b_id, "a.py")
        # Cycle 2: c ↔ d
        c_id = _insert_file(db, "c.py")
        d_id = _insert_file(db, "d.py")
        _insert_import(db, c_id, "d.py")
        _insert_import(db, d_id, "c.py")
        graph = DependencyGraph(db)
        cycles = graph.find_cycles()
        assert len(cycles) == 2

    def test_no_duplicate_cycles(self, db: IndexDatabase):
        """The same cycle must appear only once regardless of traversal order."""
        a_id = _insert_file(db, "a.py")
        b_id = _insert_file(db, "b.py")
        _insert_import(db, a_id, "b.py")
        _insert_import(db, b_id, "a.py")
        graph = DependencyGraph(db)
        cycles = graph.find_cycles()
        # Dedup check: all cycles unique
        cycle_tuples = [tuple(sorted(c)) for c in cycles]
        assert len(cycle_tuples) == len(set(cycle_tuples))

    def test_empty_graph_no_cycles(self, db: IndexDatabase):
        graph = DependencyGraph(db)
        assert graph.find_cycles() == []
