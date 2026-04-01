"""Tests for editing.transaction — FileTransaction, JournalEntry."""
from __future__ import annotations

import json
import os
import time
import unittest
from pathlib import Path

from lidco.editing.transaction import FileTransaction, JournalEntry


class TestJournalEntry(unittest.TestCase):
    def test_frozen(self):
        e = JournalEntry(path="a.txt", original_content="hi", timestamp=1.0)
        with self.assertRaises(AttributeError):
            e.path = "b.txt"  # type: ignore[misc]

    def test_fields(self):
        ts = time.time()
        e = JournalEntry(path="/tmp/f.txt", original_content="data", timestamp=ts)
        self.assertEqual(e.path, "/tmp/f.txt")
        self.assertEqual(e.original_content, "data")
        self.assertAlmostEqual(e.timestamp, ts, places=2)

    def test_none_content(self):
        e = JournalEntry(path="new.txt", original_content=None, timestamp=0.0)
        self.assertIsNone(e.original_content)


class TestFileTransactionRecord(unittest.TestCase):
    def test_record_adds_entry(self):
        txn = FileTransaction()
        txn.record("f.txt", "original")
        self.assertEqual(len(txn.entries), 1)
        self.assertEqual(txn.entries[0].path, "f.txt")
        self.assertEqual(txn.entries[0].original_content, "original")

    def test_record_none_for_new_file(self):
        txn = FileTransaction()
        txn.record("new.txt", None)
        self.assertIsNone(txn.entries[0].original_content)

    def test_multiple_records(self):
        txn = FileTransaction()
        txn.record("a.txt", "a")
        txn.record("b.txt", "b")
        self.assertEqual(len(txn.entries), 2)


class TestFileTransactionCommit(unittest.TestCase):
    def test_commit_sets_flag(self):
        txn = FileTransaction()
        self.assertFalse(txn.committed)
        txn.commit()
        self.assertTrue(txn.committed)


class TestFileTransactionRollback(unittest.TestCase):
    def test_rollback_restores_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.txt")
            Path(path).write_text("original", encoding="utf-8")
            txn = FileTransaction()
            txn.record(path, "original")
            Path(path).write_text("modified", encoding="utf-8")
            restored = txn.rollback()
            self.assertEqual(restored, 1)
            self.assertEqual(Path(path).read_text(encoding="utf-8"), "original")

    def test_rollback_deletes_new_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "new.txt")
            txn = FileTransaction()
            txn.record(path, None)
            Path(path).write_text("created", encoding="utf-8")
            restored = txn.rollback()
            self.assertEqual(restored, 1)
            self.assertFalse(Path(path).exists())

    def test_rollback_multiple_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p1 = os.path.join(tmp, "a.txt")
            p2 = os.path.join(tmp, "b.txt")
            Path(p1).write_text("aa", encoding="utf-8")
            Path(p2).write_text("bb", encoding="utf-8")
            txn = FileTransaction()
            txn.record(p1, "aa")
            txn.record(p2, "bb")
            Path(p1).write_text("XX", encoding="utf-8")
            Path(p2).write_text("YY", encoding="utf-8")
            restored = txn.rollback()
            self.assertEqual(restored, 2)
            self.assertEqual(Path(p1).read_text(encoding="utf-8"), "aa")
            self.assertEqual(Path(p2).read_text(encoding="utf-8"), "bb")


class TestFileTransactionContextManager(unittest.TestCase):
    def test_auto_commit_on_success(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ctx.txt")
            Path(path).write_text("orig", encoding="utf-8")
            with FileTransaction() as txn:
                txn.record(path, "orig")
                Path(path).write_text("new", encoding="utf-8")
            self.assertTrue(txn.committed)
            self.assertEqual(Path(path).read_text(encoding="utf-8"), "new")

    def test_auto_rollback_on_exception(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ctx.txt")
            Path(path).write_text("orig", encoding="utf-8")
            try:
                with FileTransaction() as txn:
                    txn.record(path, "orig")
                    Path(path).write_text("new", encoding="utf-8")
                    raise ValueError("boom")
            except ValueError:
                pass
            self.assertFalse(txn.committed)
            self.assertEqual(Path(path).read_text(encoding="utf-8"), "orig")


class TestFileTransactionJournalPersistence(unittest.TestCase):
    def test_journal_written(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            jpath = os.path.join(tmp, "journal.json")
            txn = FileTransaction(journal_path=jpath)
            txn.record("f.txt", "data")
            self.assertTrue(Path(jpath).exists())
            entries = json.loads(Path(jpath).read_text(encoding="utf-8"))
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["path"], "f.txt")

    def test_journal_cleaned_on_commit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            jpath = os.path.join(tmp, "journal.json")
            txn = FileTransaction(journal_path=jpath)
            txn.record("f.txt", "data")
            txn.commit()
            self.assertFalse(Path(jpath).exists())

    def test_journal_cleaned_on_rollback(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            jpath = os.path.join(tmp, "journal.json")
            txn = FileTransaction(journal_path=jpath)
            txn.record("f.txt", "data")
            txn.rollback()
            self.assertFalse(Path(jpath).exists())

    def test_no_journal_when_path_none(self):
        txn = FileTransaction()
        txn.record("f.txt", "data")
        # Should not raise


if __name__ == "__main__":
    unittest.main()
