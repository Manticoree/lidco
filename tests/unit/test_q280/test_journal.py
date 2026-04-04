"""Tests for metacog.journal."""
import unittest
from lidco.metacog.journal import LearningJournal, JournalEntry


class TestLearningJournal(unittest.TestCase):

    def setUp(self):
        self.journal = LearningJournal()

    def test_log_entry(self):
        e = self.journal.log("s1", "Always read before editing", category="technique")
        self.assertIsInstance(e, JournalEntry)
        self.assertEqual(e.session_id, "s1")
        self.assertEqual(e.category, "technique")

    def test_entries_all(self):
        self.journal.log("s1", "Lesson 1")
        self.journal.log("s2", "Lesson 2")
        self.assertEqual(len(self.journal.entries()), 2)

    def test_entries_by_session(self):
        self.journal.log("s1", "Lesson 1")
        self.journal.log("s2", "Lesson 2")
        self.assertEqual(len(self.journal.entries("s1")), 1)

    def test_search(self):
        self.journal.log("s1", "Always validate user input")
        self.journal.log("s1", "Use type hints")
        results = self.journal.search("validate")
        self.assertEqual(len(results), 1)

    def test_by_category(self):
        self.journal.log("s1", "L1", category="mistake")
        self.journal.log("s1", "L2", category="insight")
        self.assertEqual(len(self.journal.by_category("mistake")), 1)

    def test_by_tag(self):
        self.journal.log("s1", "L1", tags=["python", "testing"])
        self.journal.log("s1", "L2", tags=["javascript"])
        self.assertEqual(len(self.journal.by_tag("python")), 1)

    def test_extract_patterns(self):
        for i in range(5):
            self.journal.log("s1", "Always validate input before processing data")
        patterns = self.journal.extract_patterns()
        words = [p["word"] for p in patterns]
        self.assertIn("validate", words)

    def test_extract_patterns_empty(self):
        self.assertEqual(self.journal.extract_patterns(), [])

    def test_high_impact(self):
        self.journal.log("s1", "Critical lesson", impact="high")
        self.journal.log("s1", "Minor lesson", impact="low")
        self.assertEqual(len(self.journal.high_impact()), 1)

    def test_max_entries(self):
        journal = LearningJournal(max_entries=3)
        for i in range(5):
            journal.log("s1", f"Lesson {i}")
        self.assertEqual(len(journal.entries()), 3)

    def test_summary(self):
        self.journal.log("s1", "L1", category="insight")
        self.journal.log("s2", "L2", category="mistake")
        s = self.journal.summary()
        self.assertEqual(s["total_entries"], 2)
        self.assertEqual(s["sessions"], 2)

    def test_entry_id_increments(self):
        e1 = self.journal.log("s1", "L1")
        e2 = self.journal.log("s1", "L2")
        self.assertNotEqual(e1.entry_id, e2.entry_id)


if __name__ == "__main__":
    unittest.main()
