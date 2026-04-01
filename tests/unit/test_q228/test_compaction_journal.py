"""Tests for budget.compaction_journal."""
from __future__ import annotations

import unittest

from lidco.budget.compaction_journal import CompactionJournal, JournalEntry


class TestJournalEntry(unittest.TestCase):
    def test_frozen(self):
        entry = JournalEntry(id="abc")
        with self.assertRaises(AttributeError):
            entry.id = "x"  # type: ignore[misc]

    def test_defaults(self):
        entry = JournalEntry(id="a1")
        self.assertEqual(entry.strategy, "")
        self.assertEqual(entry.removed_indices, ())


class TestCompactionJournal(unittest.TestCase):
    def setUp(self):
        self.journal = CompactionJournal(max_entries=5)

    def test_log_creates_entry(self):
        entry = self.journal.log("trim", 10, 8, 1000, 800)
        self.assertEqual(entry.strategy, "trim")
        self.assertEqual(entry.before_count, 10)
        self.assertEqual(len(entry.id), 12)

    def test_get_entries(self):
        self.journal.log("a", 1, 1, 100, 50)
        self.journal.log("b", 2, 1, 200, 100)
        entries = self.journal.get_entries()
        self.assertEqual(len(entries), 2)

    def test_get_last(self):
        self.assertIsNone(self.journal.get_last())
        self.journal.log("x", 1, 1, 50, 30)
        last = self.journal.get_last()
        self.assertIsNotNone(last)
        self.assertEqual(last.strategy, "x")

    def test_max_entries_trimmed(self):
        for i in range(10):
            self.journal.log(f"s{i}", i, i, i * 100, i * 50)
        self.assertEqual(self.journal.total_compactions(), 5)

    def test_total_tokens_saved(self):
        self.journal.log("a", 1, 1, 1000, 600)
        self.journal.log("b", 1, 1, 500, 200)
        self.assertEqual(self.journal.total_tokens_saved(), 700)

    def test_clear(self):
        self.journal.log("x", 1, 1, 100, 50)
        self.journal.clear()
        self.assertEqual(self.journal.total_compactions(), 0)

    def test_export(self):
        self.journal.log("e", 3, 2, 300, 200, removed_indices=(1, 2))
        exported = self.journal.export()
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["removed_indices"], [1, 2])
        self.assertIn("id", exported[0])

    def test_summary_empty(self):
        self.assertIn("empty", self.journal.summary())

    def test_summary_with_data(self):
        self.journal.log("x", 1, 1, 100, 50)
        s = self.journal.summary()
        self.assertIn("1 entries", s)
        self.assertIn("50 tokens saved", s)

    def test_removed_indices_logged(self):
        entry = self.journal.log("r", 5, 3, 500, 300, removed_indices=(0, 2, 4))
        self.assertEqual(entry.removed_indices, (0, 2, 4))


if __name__ == "__main__":
    unittest.main()
