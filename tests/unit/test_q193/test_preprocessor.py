"""Tests for InputPreprocessor and Macro."""
from __future__ import annotations

import unittest

from lidco.input.preprocessor import InputPreprocessor, Macro


class TestMacro(unittest.TestCase):
    def test_frozen(self):
        m = Macro(name="test", keys=("a", "b"), recorded_at=1.0)
        with self.assertRaises(AttributeError):
            m.name = "other"  # type: ignore[misc]

    def test_fields(self):
        m = Macro(name="q", keys=("x", "y", "z"), recorded_at=42.0)
        self.assertEqual(m.name, "q")
        self.assertEqual(m.keys, ("x", "y", "z"))
        self.assertEqual(m.recorded_at, 42.0)

    def test_keys_is_tuple(self):
        m = Macro(name="a", keys=("k",), recorded_at=0.0)
        self.assertIsInstance(m.keys, tuple)


class TestExpandAbbreviation(unittest.TestCase):
    def setUp(self):
        self.p = InputPreprocessor()

    def test_single_abbreviation(self):
        result = self.p.expand_abbreviation("fn test", {"fn": "function"})
        self.assertEqual(result, "function test")

    def test_multiple_abbreviations(self):
        abbr = {"fn": "function", "ret": "return"}
        result = self.p.expand_abbreviation("fn foo ret bar", abbr)
        self.assertEqual(result, "function foo return bar")

    def test_no_match(self):
        result = self.p.expand_abbreviation("hello world", {"fn": "function"})
        self.assertEqual(result, "hello world")

    def test_empty_text(self):
        result = self.p.expand_abbreviation("", {"fn": "function"})
        self.assertEqual(result, "")

    def test_empty_abbreviations(self):
        result = self.p.expand_abbreviation("hello", {})
        self.assertEqual(result, "hello")


class TestRecordMacro(unittest.TestCase):
    def setUp(self):
        self.p = InputPreprocessor()

    def test_record_returns_macro(self):
        m = self.p.record_macro("test", ["a", "b", "c"])
        self.assertIsInstance(m, Macro)
        self.assertEqual(m.name, "test")
        self.assertEqual(m.keys, ("a", "b", "c"))

    def test_record_sets_timestamp(self):
        m = self.p.record_macro("t", ["x"])
        self.assertGreater(m.recorded_at, 0)

    def test_record_stores_in_macros(self):
        self.p.record_macro("hello", ["h", "i"])
        self.assertIn("hello", self.p._macros)

    def test_record_overwrites(self):
        self.p.record_macro("m", ["a"])
        self.p.record_macro("m", ["b"])
        self.assertEqual(self.p._macros["m"].keys, ("b",))


class TestReplayMacro(unittest.TestCase):
    def setUp(self):
        self.p = InputPreprocessor()

    def test_replay_returns_keys(self):
        m = self.p.record_macro("test", ["a", "b", "c"])
        result = self.p.replay_macro(m)
        self.assertEqual(result, ["a", "b", "c"])

    def test_replay_returns_list(self):
        m = self.p.record_macro("t", ["x"])
        result = self.p.replay_macro(m)
        self.assertIsInstance(result, list)


class TestSearchHistory(unittest.TestCase):
    def setUp(self):
        self.p = InputPreprocessor()

    def test_search_finds_matches(self):
        history = ("git commit", "git push", "python test", "git log")
        result = self.p.search_history("git", history)
        self.assertEqual(len(result), 3)

    def test_search_case_insensitive(self):
        history = ("Git Commit", "GIT PUSH")
        result = self.p.search_history("git", history)
        self.assertEqual(len(result), 2)

    def test_search_no_match(self):
        history = ("hello", "world")
        result = self.p.search_history("xyz", history)
        self.assertEqual(len(result), 0)

    def test_search_empty_history(self):
        result = self.p.search_history("test", ())
        self.assertEqual(result, ())

    def test_search_returns_tuple(self):
        result = self.p.search_history("a", ("abc",))
        self.assertIsInstance(result, tuple)


if __name__ == "__main__":
    unittest.main()
