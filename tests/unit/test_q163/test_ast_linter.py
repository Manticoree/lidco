"""Tests for ASTLinter — Task 930."""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from lidco.ast.treesitter_parser import TreeSitterParser
from lidco.ast.ast_linter import ASTLinter, LintResult


class TestLintResult(unittest.TestCase):
    def test_dataclass_defaults(self):
        r = LintResult(file_path="a.py", language="python")
        self.assertEqual(r.file_path, "a.py")
        self.assertEqual(r.language, "python")
        self.assertEqual(r.errors, [])
        self.assertEqual(r.warnings, [])
        self.assertTrue(r.valid)

    def test_with_errors(self):
        r = LintResult(file_path="b.js", language="javascript", errors=["e1"], valid=False)
        self.assertFalse(r.valid)
        self.assertEqual(len(r.errors), 1)


class TestASTLinterFallback(unittest.TestCase):
    def setUp(self):
        self.parser = TreeSitterParser()
        self.linter = ASTLinter(self.parser)

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_valid_python(self):
        result = self.linter.lint("x = 1\n", "python")
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_invalid_python(self):
        result = self.linter.lint("def foo(\n", "python")
        self.assertFalse(result.valid)
        self.assertTrue(len(result.errors) > 0)

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_bracket_mismatch(self):
        result = self.linter.lint("x = (1 + 2\n", "javascript")
        self.assertFalse(result.valid)
        self.assertTrue(any("Unclosed" in e for e in result.errors))

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_trailing_whitespace_warning(self):
        result = self.linter.lint("x = 1   \ny = 2\n", "python")
        self.assertTrue(any("Trailing whitespace" in w for w in result.warnings))

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_matched_brackets(self):
        result = self.linter.lint("x = (1 + 2)\ny = [3, 4]\nz = {'a': 1}\n", "python")
        bracket_errors = [e for e in result.errors if "bracket" in e.lower() or "Unclosed" in e or "Unmatched" in e]
        self.assertEqual(bracket_errors, [])

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_unmatched_closing(self):
        result = self.linter.lint("x = 1)\n", "javascript")
        self.assertFalse(result.valid)
        self.assertTrue(any("Unmatched" in e for e in result.errors))

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_file_success(self):
        def read_fn(path):
            return "x = 1\n"
        result = self.linter.lint_file("test.py", read_fn=read_fn)
        self.assertTrue(result.valid)
        self.assertEqual(result.language, "python")

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_file_read_error(self):
        def read_fn(path):
            raise FileNotFoundError("gone")
        result = self.linter.lint_file("missing.py", read_fn=read_fn)
        self.assertFalse(result.valid)
        self.assertTrue(any("Cannot read" in e for e in result.errors))

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_file_unknown_ext(self):
        def read_fn(path):
            return "stuff\n"
        result = self.linter.lint_file("data.xyz", read_fn=read_fn)
        self.assertEqual(result.language, "unknown")

    def test_auto_fix_suggestions_indent(self):
        r = LintResult(file_path="a.py", language="python", errors=["unexpected indent"], valid=False)
        suggestions = self.linter.auto_fix_suggestions(r)
        self.assertTrue(len(suggestions) > 0)
        self.assertTrue(any("indent" in s.lower() for s in suggestions))

    def test_auto_fix_suggestions_string(self):
        r = LintResult(file_path="a.py", language="python", errors=["unterminated string literal"], valid=False)
        suggestions = self.linter.auto_fix_suggestions(r)
        self.assertTrue(len(suggestions) > 0)

    def test_auto_fix_suggestions_syntax(self):
        r = LintResult(file_path="a.py", language="python", errors=["syntax error at line 5"], valid=False)
        suggestions = self.linter.auto_fix_suggestions(r)
        self.assertTrue(len(suggestions) > 0)

    def test_auto_fix_suggestions_empty(self):
        r = LintResult(file_path="a.py", language="python", errors=[], valid=True)
        suggestions = self.linter.auto_fix_suggestions(r)
        self.assertEqual(suggestions, [])

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_lint_strings_not_brackets(self):
        # Brackets inside strings should not count
        result = self.linter.lint('x = "hello (world"\n', "javascript")
        bracket_errors = [e for e in result.errors if "Unclosed" in e or "Unmatched" in e or "Mismatched" in e]
        self.assertEqual(bracket_errors, [])


class TestASTLinterWithTreeSitter(unittest.TestCase):
    @patch("lidco.ast.ast_linter.HAS_TREESITTER", True)
    def test_lint_delegates_to_treesitter(self):
        parser = TreeSitterParser()
        # Mock parse to return a clean result
        from lidco.ast.treesitter_parser import ParseResult
        parser.parse = lambda src, lang: ParseResult(  # type: ignore[assignment]
            language=lang, tree_available=True, node_count=5, errors=[]
        )
        parser.is_available = lambda: True  # type: ignore[assignment]
        linter = ASTLinter(parser)
        result = linter.lint("x = 1", "python")
        self.assertTrue(result.valid)
        self.assertTrue(result.language, "python")

    @patch("lidco.ast.ast_linter.HAS_TREESITTER", True)
    def test_lint_treesitter_with_errors(self):
        parser = TreeSitterParser()
        from lidco.ast.treesitter_parser import ParseResult
        parser.parse = lambda src, lang: ParseResult(  # type: ignore[assignment]
            language=lang, tree_available=True, node_count=3,
            errors=["Syntax error at line 2, col 0"]
        )
        parser.is_available = lambda: True  # type: ignore[assignment]
        linter = ASTLinter(parser)
        result = linter.lint("bad", "python")
        self.assertFalse(result.valid)
        self.assertEqual(len(result.errors), 1)


if __name__ == "__main__":
    unittest.main()
