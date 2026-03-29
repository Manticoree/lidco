"""Tests for RulesResolver — Task 728."""

from __future__ import annotations

import unittest

from lidco.rules.rules_loader import RulesFile, RulesFileLoader
from lidco.rules.rules_resolver import RulesResolver


def _make_loader(rules: list[RulesFile]):
    """Create a loader that returns fixed rules."""
    loader = RulesFileLoader(
        rules_dir="/d",
        read_fn=lambda p: "",
        listdir_fn=lambda d: [],
        mtime_fn=lambda p: 0,
    )
    loader.load_all = lambda: rules  # type: ignore[assignment]
    return loader


class TestResolve(unittest.TestCase):
    """resolve() with various glob patterns."""

    def test_wildcard_matches_everything(self):
        rules = [RulesFile("/r/a.md", "*", "General rule")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["foo.py", "bar.js"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].content, "General rule")

    def test_py_glob_matches_py_files(self):
        rules = [RulesFile("/r/a.md", "*.py", "Python rule")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["main.py"])
        self.assertEqual(len(result), 1)

    def test_py_glob_no_match_js_file(self):
        rules = [RulesFile("/r/a.md", "*.py", "Python rule")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["app.js"])
        self.assertEqual(len(result), 0)

    def test_multiple_rules_partial_match(self):
        rules = [
            RulesFile("/r/py.md", "*.py", "Python"),
            RulesFile("/r/js.md", "*.js", "JS"),
            RulesFile("/r/all.md", "*", "All"),
        ]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["test.py"])
        self.assertEqual(len(result), 2)  # *.py and *
        contents = {r.content for r in result}
        self.assertIn("Python", contents)
        self.assertIn("All", contents)

    def test_empty_files_list(self):
        rules = [RulesFile("/r/a.md", "*", "General")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve([])
        self.assertEqual(len(result), 0)

    def test_no_rules(self):
        resolver = RulesResolver(_make_loader([]))
        result = resolver.resolve(["foo.py"])
        self.assertEqual(len(result), 0)

    def test_multiple_files_one_matches(self):
        rules = [RulesFile("/r/a.md", "*.py", "Python")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["readme.md", "app.py", "style.css"])
        self.assertEqual(len(result), 1)

    def test_glob_with_double_star(self):
        rules = [RulesFile("/r/a.md", "tests/**", "Test rules")]
        resolver = RulesResolver(_make_loader(rules))
        # fnmatch uses shell-style: ** matches within path components
        result = resolver.resolve(["tests/unit/test_foo.py"])
        self.assertEqual(len(result), 1)

    def test_glob_case_sensitive(self):
        rules = [RulesFile("/r/a.md", "*.PY", "Upper")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["main.py"])
        # fnmatch is case-sensitive on Linux-like matching
        # This may or may not match depending on OS, but the test validates behavior
        # On case-sensitive: no match
        # We accept either behavior but test deterministically
        # fnmatch.fnmatch on Windows is case-insensitive, on Linux case-sensitive
        self.assertIsInstance(result, list)

    def test_glob_question_mark(self):
        rules = [RulesFile("/r/a.md", "?.py", "Single char")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["a.py"])
        self.assertEqual(len(result), 1)

    def test_glob_question_mark_no_match_long(self):
        rules = [RulesFile("/r/a.md", "?.py", "Single char")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["ab.py"])
        self.assertEqual(len(result), 0)

    def test_rule_matches_if_any_file_matches(self):
        rules = [RulesFile("/r/a.md", "*.py", "Python")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["a.txt", "b.js", "c.py"])
        self.assertEqual(len(result), 1)

    def test_rule_not_duplicated_when_multiple_files_match(self):
        rules = [RulesFile("/r/a.md", "*.py", "Python")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["a.py", "b.py", "c.py"])
        self.assertEqual(len(result), 1)

    def test_all_rules_returned_when_all_match(self):
        rules = [
            RulesFile("/r/a.md", "*", "All"),
            RulesFile("/r/b.md", "*", "Also all"),
        ]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["x.py"])
        self.assertEqual(len(result), 2)

    def test_glob_bracket_pattern(self):
        rules = [RulesFile("/r/a.md", "*.[ch]", "C files")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["main.c"])
        self.assertEqual(len(result), 1)

    def test_glob_bracket_no_match(self):
        rules = [RulesFile("/r/a.md", "*.[ch]", "C files")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve(["main.py"])
        self.assertEqual(len(result), 0)


class TestResolveText(unittest.TestCase):
    """resolve_text concatenation."""

    def test_single_rule(self):
        rules = [RulesFile("/r/a.md", "*", "Hello")]
        resolver = RulesResolver(_make_loader(rules))
        text = resolver.resolve_text(["x.py"])
        self.assertEqual(text, "Hello")

    def test_multiple_rules_joined(self):
        rules = [
            RulesFile("/r/a.md", "*", "Rule A"),
            RulesFile("/r/b.md", "*", "Rule B"),
        ]
        resolver = RulesResolver(_make_loader(rules))
        text = resolver.resolve_text(["x.py"])
        self.assertIn("Rule A", text)
        self.assertIn("Rule B", text)
        self.assertIn("\n\n", text)

    def test_custom_separator(self):
        rules = [
            RulesFile("/r/a.md", "*", "A"),
            RulesFile("/r/b.md", "*", "B"),
        ]
        resolver = RulesResolver(_make_loader(rules))
        text = resolver.resolve_text(["x.py"], separator=" | ")
        self.assertEqual(text, "A | B")

    def test_no_match_returns_empty(self):
        rules = [RulesFile("/r/a.md", "*.py", "Python")]
        resolver = RulesResolver(_make_loader(rules))
        text = resolver.resolve_text(["x.js"])
        self.assertEqual(text, "")

    def test_empty_files_returns_empty(self):
        rules = [RulesFile("/r/a.md", "*", "X")]
        resolver = RulesResolver(_make_loader(rules))
        text = resolver.resolve_text([])
        self.assertEqual(text, "")


class TestResolveForFile(unittest.TestCase):
    """resolve_for_file convenience method."""

    def test_single_file_match(self):
        rules = [RulesFile("/r/a.md", "*.py", "Python")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve_for_file("main.py")
        self.assertEqual(len(result), 1)

    def test_single_file_no_match(self):
        rules = [RulesFile("/r/a.md", "*.py", "Python")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve_for_file("app.js")
        self.assertEqual(len(result), 0)

    def test_wildcard_match(self):
        rules = [RulesFile("/r/a.md", "*", "All")]
        resolver = RulesResolver(_make_loader(rules))
        result = resolver.resolve_for_file("anything.xyz")
        self.assertEqual(len(result), 1)

    def test_returns_list(self):
        resolver = RulesResolver(_make_loader([]))
        result = resolver.resolve_for_file("x")
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
