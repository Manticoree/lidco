"""Tests for Q329 — KnowledgeUpdater."""
from __future__ import annotations

import os
import tempfile
import unittest

from lidco.knowledge.extractor import KnowledgeExtractor
from lidco.knowledge.graph import EntityType, KnowledgeGraph
from lidco.knowledge.updater import (
    FileState,
    KnowledgeUpdater,
    UpdateResult,
)


class TestFileState(unittest.TestCase):
    def test_fields(self) -> None:
        fs = FileState(path="a.py", content_hash="abc123", last_updated=1000.0)
        self.assertEqual(fs.path, "a.py")
        self.assertEqual(fs.content_hash, "abc123")
        self.assertEqual(fs.entity_ids, [])


class TestUpdateResult(unittest.TestCase):
    def test_total_changes(self) -> None:
        r = UpdateResult(entities_added=3, entities_removed=1, entities_updated=2)
        self.assertEqual(r.total_changes, 6)

    def test_defaults(self) -> None:
        r = UpdateResult()
        self.assertEqual(r.total_changes, 0)
        self.assertEqual(r.files_scanned, 0)


class TestKnowledgeUpdater(unittest.TestCase):
    def test_update_file_from_content(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        source = 'class Foo:\n    """A foo."""\n    pass\n'
        result = u.update_file("foo.py", content=source)
        self.assertEqual(result.files_changed, 1)
        self.assertGreater(result.entities_added, 0)
        # Graph should contain file entity + class entity
        entities = g.all_entities()
        names = {e.name for e in entities}
        self.assertIn("foo.py", names)
        self.assertIn("Foo", names)

    def test_update_file_no_change(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        source = 'x = 1\n'
        u.update_file("x.py", content=source)
        # Update again with same content
        result = u.update_file("x.py", content=source)
        self.assertEqual(result.files_changed, 0)

    def test_update_file_changed_content(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        u.update_file("m.py", content='class A:\n    pass\n')
        result = u.update_file("m.py", content='class B:\n    pass\n')
        self.assertEqual(result.files_changed, 1)
        self.assertGreater(result.entities_removed, 0)
        self.assertGreater(result.entities_added, 0)

    def test_update_file_from_disk(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write('def greet():\n    """Say hi."""\n    pass\n')
            f.flush()
            path = f.name
        try:
            result = u.update_file(path)
            self.assertEqual(result.files_changed, 1)
            names = {e.name for e in g.all_entities()}
            self.assertIn("greet", names)
        finally:
            os.unlink(path)

    def test_update_file_missing_file(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        result = u.update_file("/nonexistent/file.py")
        self.assertGreater(result.error_count, 0)

    def test_has_changed(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        u.update_file("a.py", content="x = 1\n")
        self.assertFalse(u.has_changed("a.py", "x = 1\n"))
        self.assertTrue(u.has_changed("a.py", "x = 2\n"))
        self.assertTrue(u.has_changed("new.py", "y = 1\n"))

    def test_tracked_files(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        u.update_file("a.py", content="x = 1\n")
        u.update_file("b.py", content="y = 2\n")
        self.assertEqual(sorted(u.tracked_files), ["a.py", "b.py"])

    def test_update_files_multiple(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f1:
            f1.write('class A:\n    pass\n')
            f1.flush()
            p1 = f1.name
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f2:
            f2.write('class B:\n    pass\n')
            f2.flush()
            p2 = f2.name
        try:
            result = u.update_files([p1, p2])
            self.assertEqual(result.files_scanned, 2)
            self.assertEqual(result.files_changed, 2)
        finally:
            os.unlink(p1)
            os.unlink(p2)

    def test_conflict_detection(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        u.update_file("a.py", content='class SharedName:\n    pass\n')
        result = u.update_file("b.py", content='class SharedName:\n    pass\n')
        self.assertGreater(len(result.conflicts), 0)
        self.assertIn("SharedName", result.conflicts[0])

    def test_resolve_conflict_keep(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        u.update_file("a.py", content='class Foo:\n    pass\n')
        entities = g.all_entities()
        eid = [e.id for e in entities if e.name == "Foo"][0]
        self.assertTrue(u.resolve_conflict(eid, keep=True))

    def test_resolve_conflict_remove(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        u.update_file("a.py", content='class Foo:\n    pass\n')
        entities = g.all_entities()
        eid = [e.id for e in entities if e.name == "Foo"][0]
        self.assertTrue(u.resolve_conflict(eid, keep=False))
        self.assertIsNone(g.get_entity(eid))

    def test_remove_stale(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        u.update_file("old.py", content='class Old:\n    pass\n')
        # Force old timestamp
        u._file_states["old.py"].last_updated = 0.0
        removed = u.remove_stale(max_age_seconds=1.0)
        self.assertGreater(removed, 0)
        self.assertNotIn("old.py", u.tracked_files)

    def test_full_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, "a.py")
            with open(p1, "w", encoding="utf-8") as f:
                f.write('class Alpha:\n    pass\n')
            p2 = os.path.join(tmpdir, "b.py")
            with open(p2, "w", encoding="utf-8") as f:
                f.write('class Beta:\n    pass\n')
            g = KnowledgeGraph()
            u = KnowledgeUpdater(g)
            result = u.full_update(tmpdir)
            self.assertEqual(result.files_scanned, 2)
            self.assertEqual(result.files_changed, 2)
            names = {e.name for e in g.all_entities()}
            self.assertIn("Alpha", names)
            self.assertIn("Beta", names)

    def test_graph_property(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        self.assertIs(u.graph, g)

    def test_contains_relationships_created(self) -> None:
        g = KnowledgeGraph()
        u = KnowledgeUpdater(g)
        u.update_file("m.py", content='class MyClass:\n    pass\n')
        rels = g.all_relationships()
        self.assertGreater(len(rels), 0)
        # File entity should have outgoing CONTAINS
        file_entity = [e for e in g.all_entities() if e.entity_type == EntityType.FILE]
        self.assertEqual(len(file_entity), 1)


if __name__ == "__main__":
    unittest.main()
