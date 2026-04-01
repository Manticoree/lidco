"""Tests for AutoComplete — task 1100."""
from __future__ import annotations

import unittest

from lidco.prompts.auto_complete import AutoComplete, Completion


class TestCompletionFrozen(unittest.TestCase):
    def test_immutable(self):
        c = Completion(text="/fix", kind="command", score=0.9)
        with self.assertRaises(AttributeError):
            c.text = "/test"  # type: ignore[misc]

    def test_fields(self):
        c = Completion("f.py", "file", 0.7)
        self.assertEqual(c.text, "f.py")
        self.assertEqual(c.kind, "file")
        self.assertEqual(c.score, 0.7)

    def test_equality(self):
        a = Completion("x", "command", 0.5)
        b = Completion("x", "command", 0.5)
        self.assertEqual(a, b)


class TestAutoCompleteInit(unittest.TestCase):
    def test_defaults(self):
        ac = AutoComplete()
        self.assertEqual(ac.commands, ())
        self.assertEqual(ac.files, ())
        self.assertEqual(ac.symbols, ())

    def test_custom(self):
        ac = AutoComplete(commands=("/fix",), files=("a.py",), symbols=("Foo",))
        self.assertEqual(ac.commands, ("/fix",))
        self.assertEqual(ac.files, ("a.py",))
        self.assertEqual(ac.symbols, ("Foo",))


class TestComplete(unittest.TestCase):
    def test_empty_prefix(self):
        self.assertEqual(AutoComplete(commands=("/fix",)).complete(""), ())

    def test_exact_match(self):
        ac = AutoComplete(commands=("/fix",))
        results = ac.complete("/fix")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].text, "/fix")
        self.assertEqual(results[0].score, 1.0)

    def test_prefix_match(self):
        ac = AutoComplete(commands=("/fix", "/find", "/format"))
        results = ac.complete("/fi")
        texts = [r.text for r in results]
        self.assertIn("/fix", texts)
        self.assertIn("/find", texts)

    def test_sorted_by_score_desc(self):
        ac = AutoComplete(commands=("/fix", "/find"), files=("fix.py",))
        results = ac.complete("/fix")
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_mixed_sources(self):
        ac = AutoComplete(commands=("/test",), files=("test.py",), symbols=("TestCase",))
        results = ac.complete("test")
        kinds = {r.kind for r in results}
        self.assertTrue(len(kinds) >= 1)

    def test_no_match(self):
        ac = AutoComplete(commands=("/fix",))
        results = ac.complete("zzz")
        self.assertEqual(results, ())

    def test_returns_tuple(self):
        result = AutoComplete().complete("x")
        self.assertIsInstance(result, tuple)


class TestAddSource(unittest.TestCase):
    def test_add_commands(self):
        ac1 = AutoComplete()
        ac2 = ac1.add_source("command", ("/new",))
        self.assertIsNot(ac1, ac2)
        self.assertEqual(ac1.commands, ())
        self.assertEqual(ac2.commands, ("/new",))

    def test_add_files(self):
        ac = AutoComplete().add_source("file", ("a.py", "b.py"))
        self.assertEqual(ac.files, ("a.py", "b.py"))

    def test_add_symbols(self):
        ac = AutoComplete().add_source("symbol", ("Foo",))
        self.assertEqual(ac.symbols, ("Foo",))

    def test_unknown_kind_raises(self):
        with self.assertRaises(ValueError):
            AutoComplete().add_source("unknown", ("x",))

    def test_appends_to_existing(self):
        ac = AutoComplete(commands=("/a",)).add_source("command", ("/b",))
        self.assertEqual(ac.commands, ("/a", "/b"))


class TestFuzzyMatch(unittest.TestCase):
    def test_empty_query(self):
        self.assertEqual(AutoComplete().fuzzy_match("", ("abc",)), ())

    def test_subsequence_match(self):
        ac = AutoComplete()
        result = ac.fuzzy_match("abc", ("aXbXc", "xyz"))
        self.assertIn("aXbXc", result)
        self.assertNotIn("xyz", result)

    def test_no_match(self):
        result = AutoComplete().fuzzy_match("zzz", ("abc", "def"))
        self.assertEqual(result, ())

    def test_sorted_by_score(self):
        result = AutoComplete().fuzzy_match("ab", ("ab", "aXb", "aXXb"))
        self.assertEqual(result[0], "ab")

    def test_case_insensitive(self):
        result = AutoComplete().fuzzy_match("abc", ("ABC", "AxBxC"))
        self.assertIn("ABC", result)


if __name__ == "__main__":
    unittest.main()
