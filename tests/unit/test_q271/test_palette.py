"""Tests for CommandPalette — Q271."""
from __future__ import annotations

import unittest

from lidco.shortcuts.palette import PaletteEntry, CommandPalette


class TestCommandPalette(unittest.TestCase):
    def setUp(self):
        self.pal = CommandPalette()

    def test_register(self):
        e = self.pal.register("save", "Save current file")
        self.assertEqual(e.command, "save")

    def test_unregister(self):
        self.pal.register("save", "Save")
        self.assertTrue(self.pal.unregister("save"))
        self.assertFalse(self.pal.unregister("save"))

    def test_search_exact(self):
        self.pal.register("save", "Save file")
        self.pal.register("open", "Open file")
        results = self.pal.search("save")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].command, "save")

    def test_search_fuzzy_subsequence(self):
        self.pal.register("format-document", "Format the document")
        results = self.pal.search("fmtdoc")
        # subsequence match
        self.assertGreater(len(results), 0)

    def test_search_no_match(self):
        self.pal.register("save", "Save file")
        results = self.pal.search("zzz")
        self.assertEqual(len(results), 0)

    def test_search_limit(self):
        for i in range(30):
            self.pal.register(f"cmd{i}", f"Command {i}")
        results = self.pal.search("cmd", limit=5)
        self.assertLessEqual(len(results), 5)

    def test_execute_records_recent(self):
        self.pal.register("save", "Save")
        self.assertTrue(self.pal.execute("save"))
        self.assertIn("save", self.pal.recent())

    def test_execute_unknown(self):
        self.assertFalse(self.pal.execute("nope"))

    def test_recent_deduplicates(self):
        self.pal.register("save", "Save")
        self.pal.execute("save")
        self.pal.execute("save")
        self.assertEqual(self.pal.recent().count("save"), 1)

    def test_by_category(self):
        self.pal.register("save", "Save", category="file")
        self.pal.register("open", "Open", category="file")
        self.pal.register("help", "Help", category="general")
        self.assertEqual(len(self.pal.by_category("file")), 2)

    def test_categories(self):
        self.pal.register("save", "Save", category="file")
        self.pal.register("help", "Help", category="general")
        cats = self.pal.categories()
        self.assertIn("file", cats)
        self.assertIn("general", cats)

    def test_all_entries(self):
        self.pal.register("a", "A")
        self.pal.register("b", "B")
        self.assertEqual(len(self.pal.all_entries()), 2)

    def test_summary(self):
        self.pal.register("a", "A")
        s = self.pal.summary()
        self.assertEqual(s["total"], 1)

    def test_search_scores_populated(self):
        self.pal.register("save", "Save file")
        results = self.pal.search("save")
        self.assertGreater(results[0].score, 0)


if __name__ == "__main__":
    unittest.main()
