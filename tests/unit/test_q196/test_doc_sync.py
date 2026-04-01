"""Tests for docgen.doc_sync — StaleDoc, SyncStatus, DocSyncEngine."""
from __future__ import annotations

import os
import tempfile
import time
import unittest

from lidco.docgen.doc_sync import DocSyncEngine, StaleDoc, SyncStatus


class TestStaleDoc(unittest.TestCase):
    def test_frozen(self):
        s = StaleDoc(path="d.md", reason="old", last_code_change="t1", last_doc_change="t2")
        with self.assertRaises(AttributeError):
            s.path = "x"  # type: ignore[misc]

    def test_fields(self):
        s = StaleDoc("docs/api.md", "code changed", "2026-01-02", "2026-01-01")
        self.assertEqual(s.path, "docs/api.md")
        self.assertEqual(s.reason, "code changed")
        self.assertEqual(s.last_code_change, "2026-01-02")
        self.assertEqual(s.last_doc_change, "2026-01-01")

    def test_equality(self):
        a = StaleDoc("p", "r", "c", "d")
        b = StaleDoc("p", "r", "c", "d")
        self.assertEqual(a, b)


class TestSyncStatus(unittest.TestCase):
    def test_frozen(self):
        s = SyncStatus(total_docs=5, stale=2, fresh=3, stale_docs=())
        with self.assertRaises(AttributeError):
            s.total_docs = 10  # type: ignore[misc]

    def test_fields(self):
        sd = StaleDoc("d.md", "old", "c", "d")
        s = SyncStatus(10, 1, 9, (sd,))
        self.assertEqual(s.total_docs, 10)
        self.assertEqual(s.stale, 1)
        self.assertEqual(s.fresh, 9)
        self.assertEqual(len(s.stale_docs), 1)


class TestDocSyncEngine(unittest.TestCase):
    def _make_project(self):
        td = tempfile.mkdtemp()
        docs_dir = os.path.join(td, "docs")
        src_dir = os.path.join(td, "src")
        os.makedirs(docs_dir)
        os.makedirs(src_dir)
        return td, docs_dir, src_dir

    def test_check_staleness_no_docs(self):
        with tempfile.TemporaryDirectory() as td:
            engine = DocSyncEngine(td)
            status = engine.check_staleness()
            self.assertEqual(status.total_docs, 0)
            self.assertEqual(status.stale, 0)

    def test_check_staleness_fresh(self):
        td, docs_dir, src_dir = self._make_project()
        try:
            # Create source first
            src_file = os.path.join(src_dir, "mod.py")
            with open(src_file, "w") as f:
                f.write("x = 1\n")
            time.sleep(0.05)
            # Create doc after source
            doc_file = os.path.join(docs_dir, "api.md")
            with open(doc_file, "w") as f:
                f.write("# API\n")
            engine = DocSyncEngine(td)
            status = engine.check_staleness()
            self.assertEqual(status.total_docs, 1)
            self.assertEqual(status.fresh, 1)
            self.assertEqual(status.stale, 0)
        finally:
            import shutil
            shutil.rmtree(td)

    def test_check_staleness_stale(self):
        td, docs_dir, src_dir = self._make_project()
        try:
            # Create doc first
            doc_file = os.path.join(docs_dir, "api.md")
            with open(doc_file, "w") as f:
                f.write("# API\n")
            time.sleep(0.05)
            # Create source after doc
            src_file = os.path.join(src_dir, "mod.py")
            with open(src_file, "w") as f:
                f.write("x = 1\n")
            engine = DocSyncEngine(td)
            status = engine.check_staleness()
            self.assertEqual(status.total_docs, 1)
            self.assertEqual(status.stale, 1)
            self.assertEqual(len(status.stale_docs), 1)
        finally:
            import shutil
            shutil.rmtree(td)

    def test_find_stale_no_docs_dir(self):
        engine = DocSyncEngine("/nonexistent")
        result = engine.find_stale("/nonexistent/docs", "/nonexistent/src")
        self.assertEqual(result, ())

    def test_find_stale_returns_tuple(self):
        with tempfile.TemporaryDirectory() as td:
            engine = DocSyncEngine(td)
            result = engine.find_stale(
                os.path.join(td, "docs"), os.path.join(td, "src")
            )
            self.assertIsInstance(result, tuple)

    def test_check_staleness_returns_sync_status(self):
        with tempfile.TemporaryDirectory() as td:
            engine = DocSyncEngine(td)
            result = engine.check_staleness()
            self.assertIsInstance(result, SyncStatus)

    def test_stale_doc_has_reason(self):
        td, docs_dir, src_dir = self._make_project()
        try:
            doc_file = os.path.join(docs_dir, "old.md")
            with open(doc_file, "w") as f:
                f.write("# Old\n")
            time.sleep(0.05)
            src_file = os.path.join(src_dir, "new.py")
            with open(src_file, "w") as f:
                f.write("x = 1\n")
            engine = DocSyncEngine(td)
            status = engine.check_staleness()
            if status.stale_docs:
                self.assertIn("older", status.stale_docs[0].reason)
        finally:
            import shutil
            shutil.rmtree(td)

    def test_ignores_non_doc_files(self):
        td, docs_dir, src_dir = self._make_project()
        try:
            # Put a .py file in docs (should be ignored)
            with open(os.path.join(docs_dir, "script.py"), "w") as f:
                f.write("pass\n")
            engine = DocSyncEngine(td)
            status = engine.check_staleness()
            self.assertEqual(status.total_docs, 0)
        finally:
            import shutil
            shutil.rmtree(td)

    def test_stale_doc_different_not_equal(self):
        a = StaleDoc("a.md", "r", "c", "d")
        b = StaleDoc("b.md", "r", "c", "d")
        self.assertNotEqual(a, b)

    def test_sync_status_equality(self):
        a = SyncStatus(5, 2, 3, ())
        b = SyncStatus(5, 2, 3, ())
        self.assertEqual(a, b)

    def test_find_stale_no_src_dir(self):
        with tempfile.TemporaryDirectory() as td:
            docs_dir = os.path.join(td, "docs")
            os.makedirs(docs_dir)
            with open(os.path.join(docs_dir, "a.md"), "w") as f:
                f.write("# A\n")
            engine = DocSyncEngine(td)
            result = engine.find_stale(docs_dir, os.path.join(td, "nosrc"))
            self.assertEqual(result, ())

    def test_rst_files_counted(self):
        td, docs_dir, src_dir = self._make_project()
        try:
            with open(os.path.join(docs_dir, "guide.rst"), "w") as f:
                f.write("Guide\n=====\n")
            engine = DocSyncEngine(td)
            status = engine.check_staleness()
            self.assertEqual(status.total_docs, 1)
        finally:
            import shutil
            shutil.rmtree(td)

    def test_txt_files_counted(self):
        td, docs_dir, src_dir = self._make_project()
        try:
            with open(os.path.join(docs_dir, "notes.txt"), "w") as f:
                f.write("Notes\n")
            engine = DocSyncEngine(td)
            status = engine.check_staleness()
            self.assertEqual(status.total_docs, 1)
        finally:
            import shutil
            shutil.rmtree(td)

    def test_multiple_docs(self):
        td, docs_dir, src_dir = self._make_project()
        try:
            for name in ("a.md", "b.md", "c.md"):
                with open(os.path.join(docs_dir, name), "w") as f:
                    f.write(f"# {name}\n")
            engine = DocSyncEngine(td)
            status = engine.check_staleness()
            self.assertEqual(status.total_docs, 3)
        finally:
            import shutil
            shutil.rmtree(td)


class TestDocSyncAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.docgen import doc_sync

        self.assertIn("StaleDoc", doc_sync.__all__)
        self.assertIn("SyncStatus", doc_sync.__all__)
        self.assertIn("DocSyncEngine", doc_sync.__all__)


if __name__ == "__main__":
    unittest.main()
