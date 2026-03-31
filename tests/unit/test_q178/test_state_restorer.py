"""Tests for StateRestorer."""
import unittest
from unittest.mock import MagicMock

from lidco.resilience.crash_journal import JournalEntry
from lidco.resilience.state_restorer import StateRestorer, RestoreResult


class TestRestoreResult(unittest.TestCase):
    def test_defaults(self):
        r = RestoreResult()
        self.assertEqual(r.restored_steps, 0)
        self.assertEqual(r.skipped_steps, 0)
        self.assertEqual(r.status, "ok")
        self.assertEqual(r.errors, [])

    def test_custom_values(self):
        r = RestoreResult(restored_steps=3, skipped_steps=1, status="restored")
        self.assertEqual(r.restored_steps, 3)
        self.assertEqual(r.skipped_steps, 1)


class TestStateRestorer(unittest.TestCase):
    def setUp(self):
        self.restorer = StateRestorer()

    def test_empty_entries(self):
        result = self.restorer.restore([])
        self.assertEqual(result.status, "nothing_to_restore")
        self.assertEqual(result.restored_steps, 0)
        self.assertEqual(result.skipped_steps, 0)

    def test_all_completed_entries(self):
        entries = [
            JournalEntry(id="1", action="a", completed=True),
            JournalEntry(id="2", action="b", completed=True),
        ]
        result = self.restorer.restore(entries)
        self.assertEqual(result.skipped_steps, 2)
        self.assertEqual(result.restored_steps, 0)
        self.assertEqual(result.status, "all_skipped")

    def test_incomplete_entries_restored(self):
        entries = [
            JournalEntry(id="1", action="a", completed=False),
            JournalEntry(id="2", action="b", completed=False),
        ]
        result = self.restorer.restore(entries)
        self.assertEqual(result.restored_steps, 2)
        self.assertEqual(result.skipped_steps, 0)
        self.assertEqual(result.status, "restored")

    def test_mixed_entries(self):
        entries = [
            JournalEntry(id="1", action="a", completed=True),
            JournalEntry(id="2", action="b", completed=False),
            JournalEntry(id="3", action="c", completed=True),
        ]
        result = self.restorer.restore(entries)
        self.assertEqual(result.restored_steps, 1)
        self.assertEqual(result.skipped_steps, 2)
        self.assertEqual(result.status, "restored")

    def test_with_git_state(self):
        entries = [JournalEntry(id="1", action="a", completed=False)]
        result = self.restorer.restore(entries, git_state={"branch": "main"})
        self.assertEqual(result.restored_steps, 1)
        self.assertEqual(result.status, "restored")

    def test_handler_called(self):
        handler = MagicMock()
        self.restorer.register_handler("deploy", handler)
        entries = [JournalEntry(id="1", action="deploy", completed=False)]
        self.restorer.restore(entries)
        handler.assert_called_once()

    def test_handler_receives_entry_and_git_state(self):
        handler = MagicMock()
        self.restorer.register_handler("build", handler)
        entry = JournalEntry(id="x", action="build", completed=False)
        git_state = {"branch": "dev"}
        self.restorer.restore([entry], git_state=git_state)
        handler.assert_called_once_with(entry, git_state)

    def test_handler_not_called_for_completed(self):
        handler = MagicMock()
        self.restorer.register_handler("deploy", handler)
        entries = [JournalEntry(id="1", action="deploy", completed=True)]
        self.restorer.restore(entries)
        handler.assert_not_called()

    def test_handler_exception_recorded(self):
        handler = MagicMock(side_effect=RuntimeError("boom"))
        self.restorer.register_handler("fail", handler)
        entries = [JournalEntry(id="1", action="fail", completed=False)]
        result = self.restorer.restore(entries)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("boom", result.errors[0])

    def test_all_fail_status(self):
        handler = MagicMock(side_effect=RuntimeError("err"))
        self.restorer.register_handler("x", handler)
        entries = [
            JournalEntry(id="1", action="x", completed=False),
            JournalEntry(id="2", action="x", completed=False),
        ]
        result = self.restorer.restore(entries)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.restored_steps, 0)

    def test_partial_fail_status(self):
        call_count = [0]
        def flaky(entry, git_state):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("fail")
        self.restorer.register_handler("x", flaky)
        entries = [
            JournalEntry(id="1", action="x", completed=False),
            JournalEntry(id="2", action="x", completed=False),
        ]
        result = self.restorer.restore(entries)
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.restored_steps, 1)
        self.assertEqual(len(result.errors), 1)

    def test_no_handler_still_counts(self):
        entries = [JournalEntry(id="1", action="unknown", completed=False)]
        result = self.restorer.restore(entries)
        self.assertEqual(result.restored_steps, 1)

    def test_register_multiple_handlers(self):
        h1 = MagicMock()
        h2 = MagicMock()
        self.restorer.register_handler("a", h1)
        self.restorer.register_handler("b", h2)
        entries = [
            JournalEntry(id="1", action="a", completed=False),
            JournalEntry(id="2", action="b", completed=False),
        ]
        self.restorer.restore(entries)
        h1.assert_called_once()
        h2.assert_called_once()

    def test_errors_list_independent(self):
        r1 = RestoreResult()
        r2 = RestoreResult()
        r1.errors.append("err1")
        self.assertEqual(r2.errors, [])

    def test_single_entry_restored(self):
        result = self.restorer.restore([JournalEntry(id="z", action="op", completed=False)])
        self.assertEqual(result.restored_steps, 1)
        self.assertEqual(result.status, "restored")

    def test_single_entry_skipped(self):
        result = self.restorer.restore([JournalEntry(id="z", action="op", completed=True)])
        self.assertEqual(result.skipped_steps, 1)
        self.assertEqual(result.status, "all_skipped")

    def test_git_state_none_default(self):
        handler = MagicMock()
        self.restorer.register_handler("a", handler)
        entries = [JournalEntry(id="1", action="a", completed=False)]
        self.restorer.restore(entries)
        handler.assert_called_once_with(entries[0], None)

    def test_large_batch(self):
        entries = [JournalEntry(id=str(i), action="op", completed=False) for i in range(50)]
        result = self.restorer.restore(entries)
        self.assertEqual(result.restored_steps, 50)

    def test_restore_result_mutable(self):
        r = RestoreResult()
        r.restored_steps = 10
        r.status = "custom"
        self.assertEqual(r.restored_steps, 10)
        self.assertEqual(r.status, "custom")


if __name__ == "__main__":
    unittest.main()
