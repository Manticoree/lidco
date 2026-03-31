"""Tests for CrashJournal."""
import json
import os
import tempfile
import unittest

from lidco.resilience.crash_journal import CrashJournal, JournalEntry


class TestJournalEntry(unittest.TestCase):
    def test_default_fields(self):
        entry = JournalEntry()
        self.assertIsInstance(entry.id, str)
        self.assertGreater(entry.timestamp, 0)
        self.assertEqual(entry.action, "")
        self.assertEqual(entry.state, {})
        self.assertFalse(entry.completed)

    def test_custom_fields(self):
        entry = JournalEntry(id="abc", timestamp=1.0, action="deploy", state={"v": 1}, completed=True)
        self.assertEqual(entry.id, "abc")
        self.assertEqual(entry.action, "deploy")
        self.assertTrue(entry.completed)

    def test_to_dict(self):
        entry = JournalEntry(id="x", timestamp=2.0, action="test", state={"k": "v"}, completed=False)
        d = entry.to_dict()
        self.assertEqual(d["id"], "x")
        self.assertEqual(d["action"], "test")
        self.assertFalse(d["completed"])

    def test_from_dict(self):
        data = {"id": "y", "timestamp": 3.0, "action": "build", "state": {}, "completed": True}
        entry = JournalEntry.from_dict(data)
        self.assertEqual(entry.id, "y")
        self.assertTrue(entry.completed)

    def test_from_dict_missing_fields(self):
        entry = JournalEntry.from_dict({})
        self.assertFalse(entry.completed)
        self.assertEqual(entry.action, "")


class TestCrashJournal(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.journal = CrashJournal(self.tmpdir)

    def test_write_entry(self):
        entry = JournalEntry(action="step1")
        eid = self.journal.write_entry(entry)
        self.assertEqual(eid, entry.id)
        self.assertEqual(len(self.journal.all_entries()), 1)

    def test_complete_entry(self):
        entry = JournalEntry(action="step1")
        self.journal.write_entry(entry)
        self.journal.complete(entry.id)
        got = self.journal.get_entry(entry.id)
        self.assertTrue(got.completed)

    def test_complete_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.journal.complete("nonexistent")

    def test_rollback_entry(self):
        entry = JournalEntry(action="step1")
        self.journal.write_entry(entry)
        self.journal.rollback(entry.id)
        self.assertIsNone(self.journal.get_entry(entry.id))
        self.assertEqual(len(self.journal.all_entries()), 0)

    def test_rollback_unknown_raises(self):
        with self.assertRaises(KeyError):
            self.journal.rollback("nonexistent")

    def test_on_startup_returns_incomplete(self):
        e1 = JournalEntry(action="a")
        e2 = JournalEntry(action="b")
        self.journal.write_entry(e1)
        self.journal.write_entry(e2)
        self.journal.complete(e1.id)
        incomplete = self.journal.on_startup()
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0].id, e2.id)

    def test_on_startup_empty(self):
        self.assertEqual(self.journal.on_startup(), [])

    def test_clear(self):
        self.journal.write_entry(JournalEntry(action="x"))
        self.journal.write_entry(JournalEntry(action="y"))
        self.journal.clear()
        self.assertEqual(len(self.journal.all_entries()), 0)

    def test_persistence_across_instances(self):
        e = JournalEntry(action="persist")
        self.journal.write_entry(e)
        journal2 = CrashJournal(self.tmpdir)
        self.assertEqual(len(journal2.all_entries()), 1)
        self.assertEqual(journal2.all_entries()[0].action, "persist")

    def test_persistence_after_complete(self):
        e = JournalEntry(action="done")
        self.journal.write_entry(e)
        self.journal.complete(e.id)
        journal2 = CrashJournal(self.tmpdir)
        got = journal2.get_entry(e.id)
        self.assertTrue(got.completed)

    def test_persistence_after_rollback(self):
        e = JournalEntry(action="gone")
        self.journal.write_entry(e)
        self.journal.rollback(e.id)
        journal2 = CrashJournal(self.tmpdir)
        self.assertEqual(len(journal2.all_entries()), 0)

    def test_persistence_after_clear(self):
        self.journal.write_entry(JournalEntry(action="x"))
        self.journal.clear()
        journal2 = CrashJournal(self.tmpdir)
        self.assertEqual(len(journal2.all_entries()), 0)

    def test_journal_dir_property(self):
        self.assertEqual(self.journal.journal_dir, self.tmpdir)

    def test_corrupt_journal_file(self):
        jfile = os.path.join(self.tmpdir, "journal.json")
        with open(jfile, "w") as f:
            f.write("NOT JSON")
        journal = CrashJournal(self.tmpdir)
        self.assertEqual(len(journal.all_entries()), 0)

    def test_multiple_entries_order(self):
        for i in range(5):
            self.journal.write_entry(JournalEntry(action=f"step{i}"))
        self.assertEqual(len(self.journal.all_entries()), 5)

    def test_get_entry_returns_none_for_missing(self):
        self.assertIsNone(self.journal.get_entry("missing"))

    def test_write_preserves_state(self):
        e = JournalEntry(action="stateful", state={"key": "value", "n": 42})
        self.journal.write_entry(e)
        got = self.journal.get_entry(e.id)
        self.assertEqual(got.state, {"key": "value", "n": 42})

    def test_creates_directory(self):
        newdir = os.path.join(self.tmpdir, "sub", "dir")
        journal = CrashJournal(newdir)
        self.assertTrue(os.path.isdir(newdir))

    def test_complete_preserves_other_fields(self):
        e = JournalEntry(action="myaction", state={"x": 1})
        self.journal.write_entry(e)
        self.journal.complete(e.id)
        got = self.journal.get_entry(e.id)
        self.assertEqual(got.action, "myaction")
        self.assertEqual(got.state, {"x": 1})


if __name__ == "__main__":
    unittest.main()
