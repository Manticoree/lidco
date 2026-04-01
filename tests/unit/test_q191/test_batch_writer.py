"""Tests for editing.batch_writer — BatchWriter, FileOp, BatchPlan, BatchResult."""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from lidco.editing.batch_writer import BatchPlan, BatchResult, BatchWriter, FileOp


class TestFileOp(unittest.TestCase):
    def test_frozen(self):
        op = FileOp(action="WRITE", path="a.txt", content="data")
        with self.assertRaises(AttributeError):
            op.action = "DELETE"  # type: ignore[misc]

    def test_fields(self):
        op = FileOp(action="DELETE", path="/tmp/x")
        self.assertEqual(op.action, "DELETE")
        self.assertEqual(op.path, "/tmp/x")
        self.assertEqual(op.content, "")

    def test_equality(self):
        a = FileOp("WRITE", "f.txt", "data")
        b = FileOp("WRITE", "f.txt", "data")
        self.assertEqual(a, b)


class TestBatchPlan(unittest.TestCase):
    def test_frozen(self):
        plan = BatchPlan(operations=(), total=0)
        with self.assertRaises(AttributeError):
            plan.total = 5  # type: ignore[misc]

    def test_fields(self):
        ops = (FileOp("WRITE", "a.txt", "x"),)
        plan = BatchPlan(operations=ops, total=1)
        self.assertEqual(plan.total, 1)
        self.assertEqual(len(plan.operations), 1)


class TestBatchResult(unittest.TestCase):
    def test_frozen(self):
        r = BatchResult(success=True, completed=1, failed=0, errors=())
        with self.assertRaises(AttributeError):
            r.success = False  # type: ignore[misc]

    def test_fields(self):
        r = BatchResult(success=False, completed=0, failed=1, errors=("err",))
        self.assertFalse(r.success)
        self.assertEqual(r.failed, 1)
        self.assertEqual(r.errors, ("err",))


class TestBatchWriterImmutability(unittest.TestCase):
    def test_write_returns_new(self):
        w1 = BatchWriter()
        w2 = w1.write("a.txt", "data")
        self.assertIsNot(w1, w2)
        self.assertEqual(len(w1.operations), 0)
        self.assertEqual(len(w2.operations), 1)

    def test_delete_returns_new(self):
        w1 = BatchWriter()
        w2 = w1.delete("a.txt")
        self.assertIsNot(w1, w2)
        self.assertEqual(w2.operations[0].action, "DELETE")

    def test_create_dir_returns_new(self):
        w1 = BatchWriter()
        w2 = w1.create_dir("/tmp/mydir")
        self.assertIsNot(w1, w2)
        self.assertEqual(w2.operations[0].action, "MKDIR")

    def test_chain_builds(self):
        w = BatchWriter().write("a.txt", "x").delete("b.txt").create_dir("d")
        self.assertEqual(len(w.operations), 3)


class TestBatchWriterDryRun(unittest.TestCase):
    def test_dry_run_empty(self):
        plan = BatchWriter().dry_run()
        self.assertIsInstance(plan, BatchPlan)
        self.assertEqual(plan.total, 0)

    def test_dry_run_counts(self):
        w = BatchWriter().write("a", "x").delete("b")
        plan = w.dry_run()
        self.assertEqual(plan.total, 2)
        self.assertEqual(len(plan.operations), 2)


class TestBatchWriterExecuteWrite(unittest.TestCase):
    def test_write_creates_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.txt")
            result = BatchWriter().write(path, "hello").execute()
            self.assertTrue(result.success)
            self.assertEqual(result.completed, 1)
            self.assertEqual(result.failed, 0)
            self.assertEqual(Path(path).read_text(encoding="utf-8"), "hello")

    def test_write_creates_parent_dirs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "deep", "out.txt")
            result = BatchWriter().write(path, "nested").execute()
            self.assertTrue(result.success)
            self.assertTrue(Path(path).exists())


class TestBatchWriterExecuteDelete(unittest.TestCase):
    def test_delete_existing_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "del.txt")
            Path(path).write_text("bye", encoding="utf-8")
            result = BatchWriter().delete(path).execute()
            self.assertTrue(result.success)
            self.assertFalse(Path(path).exists())

    def test_delete_missing_file_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "missing.txt")
            result = BatchWriter().delete(path).execute()
            self.assertFalse(result.success)
            self.assertEqual(result.failed, 1)
            self.assertTrue(len(result.errors) > 0)


class TestBatchWriterExecuteMkdir(unittest.TestCase):
    def test_mkdir_creates_dir(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "newdir")
            result = BatchWriter().create_dir(path).execute()
            self.assertTrue(result.success)
            self.assertTrue(Path(path).is_dir())

    def test_mkdir_nested(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a", "b", "c")
            result = BatchWriter().create_dir(path).execute()
            self.assertTrue(result.success)
            self.assertTrue(Path(path).is_dir())


class TestBatchWriterExecuteMixed(unittest.TestCase):
    def test_mixed_operations(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "subdir")
            f = os.path.join(tmp, "subdir", "file.txt")
            result = BatchWriter().create_dir(d).write(f, "data").execute()
            self.assertTrue(result.success)
            self.assertEqual(result.completed, 2)
            self.assertEqual(Path(f).read_text(encoding="utf-8"), "data")


if __name__ == "__main__":
    unittest.main()
