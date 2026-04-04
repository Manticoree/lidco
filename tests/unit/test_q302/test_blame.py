"""Tests for lidco.githistory.blame."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from lidco.githistory.blame import Annotation, BlameIntelligence, BlameLine


class TestBlameLine(unittest.TestCase):
    def test_fields(self):
        bl = BlameLine(hash="abc", author="Alice", date=datetime(2026, 1, 1), line_no=10, content="x = 1")
        self.assertEqual(bl.hash, "abc")
        self.assertEqual(bl.line_no, 10)

    def test_immutable(self):
        bl = BlameLine(hash="abc", author="A", date=datetime(2026, 1, 1), line_no=1, content="x")
        with self.assertRaises(AttributeError):
            bl.hash = "new"  # type: ignore[misc]


class TestAnnotation(unittest.TestCase):
    def test_defaults(self):
        a = Annotation(line_no=1, content="x", author="A", hash="h", date=datetime(2026, 1, 1))
        self.assertEqual(a.age_days, 0.0)

    def test_custom_age(self):
        a = Annotation(line_no=1, content="x", author="A", hash="h", date=datetime(2026, 1, 1), age_days=5.5)
        self.assertEqual(a.age_days, 5.5)


class TestBlameIntelligence(unittest.TestCase):
    def setUp(self):
        self.bi = BlameIntelligence()
        d = datetime(2026, 1, 1)
        self.lines = [
            BlameLine(hash="c1", author="Alice", date=d, line_no=1, content="import os"),
            BlameLine(hash="c2", author="Bob", date=d + timedelta(days=1), line_no=2, content="x = 1"),
            BlameLine(hash="c3", author="Alice", date=d + timedelta(days=2), line_no=3, content="y = 2"),
        ]
        self.bi.set_blame("main.py", self.lines)
        self.bi.set_commit_message("c1", "initial commit")
        self.bi.set_commit_message("c2", "Run black formatter")
        self.bi.set_commit_message("c3", "add feature X")

    def test_blame_all_lines(self):
        result = self.bi.blame("main.py")
        self.assertEqual(len(result), 3)

    def test_blame_range(self):
        result = self.bi.blame("main.py", (1, 2))
        self.assertEqual(len(result), 2)

    def test_blame_unknown_file(self):
        result = self.bi.blame("unknown.py")
        self.assertEqual(result, [])

    def test_skip_formatting(self):
        all_lines = self.bi.blame("main.py")
        filtered = self.bi.skip_formatting(all_lines)
        # c2 has "black formatter" which matches "format" pattern
        hashes = [bl.hash for bl in filtered]
        self.assertNotIn("c2", hashes)
        self.assertIn("c1", hashes)
        self.assertIn("c3", hashes)

    def test_skip_formatting_no_messages(self):
        bi = BlameIntelligence()
        lines = [BlameLine(hash="x", author="A", date=datetime(2026, 1, 1), line_no=1, content="a")]
        result = bi.skip_formatting(lines)
        # No commit messages registered, so nothing is skipped
        self.assertEqual(len(result), 1)

    def test_find_original_author_skips_format(self):
        author = self.bi.find_original_author("main.py", 2)
        # Line 2 was by Bob (c2, formatting), but skip_formatting filters it out
        # No non-formatting commit touched line 2 so it falls back to Bob
        self.assertEqual(author, "Bob")

    def test_find_original_author_meaningful(self):
        author = self.bi.find_original_author("main.py", 1)
        self.assertEqual(author, "Alice")

    def test_find_original_author_unknown(self):
        author = self.bi.find_original_author("main.py", 99)
        self.assertEqual(author, "unknown")

    def test_annotate_returns_annotations(self):
        result = self.bi.annotate("main.py")
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], Annotation)

    def test_annotate_age_days_positive(self):
        result = self.bi.annotate("main.py")
        for a in result:
            self.assertGreater(a.age_days, 0)

    def test_annotate_empty_file(self):
        result = self.bi.annotate("nonexistent.py")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
