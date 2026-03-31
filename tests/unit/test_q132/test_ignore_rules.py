"""Tests for Q132 IgnoreRules."""
from __future__ import annotations
import unittest
from lidco.fs.ignore_rules import IgnoreRules, IgnoreRule


class TestIgnoreRule(unittest.TestCase):
    def test_defaults(self):
        rule = IgnoreRule(pattern="*.py")
        self.assertFalse(rule.negated)

    def test_negated(self):
        rule = IgnoreRule(pattern="*.py", negated=True)
        self.assertTrue(rule.negated)


class TestIgnoreRules(unittest.TestCase):
    def setUp(self):
        self.rules = IgnoreRules()

    def test_empty(self):
        self.assertFalse(self.rules.is_ignored("any/path.py"))

    def test_add_and_ignore(self):
        self.rules.add("*.pyc")
        self.assertTrue(self.rules.is_ignored("main.pyc"))

    def test_wildcard_matches_any_dir(self):
        self.rules.add("__pycache__")
        self.assertTrue(self.rules.is_ignored("src/__pycache__"))

    def test_does_not_match_other(self):
        self.rules.add("*.pyc")
        self.assertFalse(self.rules.is_ignored("main.py"))

    def test_comment_ignored(self):
        self.rules.add("# this is a comment")
        self.assertEqual(len(self.rules), 0)

    def test_blank_line_ignored(self):
        self.rules.add("   ")
        self.assertEqual(len(self.rules), 0)

    def test_load_gitignore(self):
        gitignore = "*.log\n# comment\ndist/\n\n"
        self.rules.load_gitignore(gitignore)
        self.assertTrue(self.rules.is_ignored("error.log"))
        self.assertTrue(self.rules.is_ignored("dist/bundle.js"))

    def test_negation_overrides(self):
        self.rules.add("*.log")
        self.rules.add("!important.log")
        self.assertFalse(self.rules.is_ignored("important.log"))

    def test_dir_pattern(self):
        self.rules.add("node_modules/")
        self.assertTrue(self.rules.is_ignored("node_modules/package.json"))

    def test_filter(self):
        self.rules.add("*.log")
        self.rules.add("*.tmp")
        paths = ["main.py", "error.log", "debug.tmp", "utils.py"]
        filtered = self.rules.filter(paths)
        self.assertIn("main.py", filtered)
        self.assertIn("utils.py", filtered)
        self.assertNotIn("error.log", filtered)
        self.assertNotIn("debug.tmp", filtered)

    def test_len(self):
        self.rules.add("*.log")
        self.rules.add("*.tmp")
        self.assertEqual(len(self.rules), 2)

    def test_init_with_patterns(self):
        rules = IgnoreRules(patterns=["*.log", "dist/"])
        self.assertEqual(len(rules), 2)
        self.assertTrue(rules.is_ignored("error.log"))

    def test_gitignore_negation(self):
        content = "*.txt\n!important.txt"
        self.rules.load_gitignore(content)
        self.assertTrue(self.rules.is_ignored("readme.txt"))
        self.assertFalse(self.rules.is_ignored("important.txt"))

    def test_double_star_like_pattern(self):
        self.rules.add("*.min.js")
        self.assertTrue(self.rules.is_ignored("app.min.js"))
        self.assertFalse(self.rules.is_ignored("app.js"))

    def test_filter_returns_all_if_no_rules(self):
        paths = ["a.py", "b.py"]
        self.assertEqual(self.rules.filter(paths), paths)

    def test_filter_empty_list(self):
        self.rules.add("*.log")
        self.assertEqual(self.rules.filter([]), [])

    def test_path_with_slash_pattern(self):
        self.rules.add("build/")
        self.assertTrue(self.rules.is_ignored("build/output.js"))

    def test_exact_name_pattern(self):
        self.rules.add(".env")
        self.assertTrue(self.rules.is_ignored(".env"))
        self.assertTrue(self.rules.is_ignored("app/.env"))


if __name__ == "__main__":
    unittest.main()
