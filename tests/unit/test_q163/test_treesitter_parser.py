"""Tests for TreeSitterParser — Task 927."""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from lidco.ast.treesitter_parser import TreeSitterParser, ParseResult, _EXTENSION_MAP


class TestParseResult(unittest.TestCase):
    def test_dataclass_fields(self):
        pr = ParseResult(language="python", tree_available=False, node_count=10)
        self.assertEqual(pr.language, "python")
        self.assertFalse(pr.tree_available)
        self.assertEqual(pr.node_count, 10)
        self.assertEqual(pr.errors, [])
        self.assertEqual(pr.source_path, "")

    def test_with_errors(self):
        pr = ParseResult(language="go", tree_available=True, node_count=5, errors=["e1"])
        self.assertEqual(pr.errors, ["e1"])


class TestTreeSitterParserNoTS(unittest.TestCase):
    """Tests with tree-sitter NOT available (regex fallback)."""

    def setUp(self):
        self.parser = TreeSitterParser()

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    def test_is_available_false(self):
        self.assertFalse(self.parser.is_available())

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    def test_supported_languages_empty(self):
        self.assertEqual(self.parser.supported_languages(), [])

    def test_detect_language_python(self):
        self.assertEqual(self.parser.detect_language("foo.py"), "python")

    def test_detect_language_javascript(self):
        self.assertEqual(self.parser.detect_language("app.js"), "javascript")

    def test_detect_language_typescript(self):
        self.assertEqual(self.parser.detect_language("index.ts"), "typescript")

    def test_detect_language_go(self):
        self.assertEqual(self.parser.detect_language("main.go"), "go")

    def test_detect_language_rust(self):
        self.assertEqual(self.parser.detect_language("lib.rs"), "rust")

    def test_detect_language_cpp(self):
        self.assertEqual(self.parser.detect_language("main.cpp"), "cpp")
        self.assertEqual(self.parser.detect_language("util.cc"), "cpp")

    def test_detect_language_c(self):
        self.assertEqual(self.parser.detect_language("main.c"), "c")

    def test_detect_language_csharp(self):
        self.assertEqual(self.parser.detect_language("Program.cs"), "c_sharp")

    def test_detect_language_java(self):
        self.assertEqual(self.parser.detect_language("Main.java"), "java")

    def test_detect_language_ruby(self):
        self.assertEqual(self.parser.detect_language("app.rb"), "ruby")

    def test_detect_language_unknown(self):
        self.assertIsNone(self.parser.detect_language("readme.txt"))

    def test_detect_language_no_ext(self):
        self.assertIsNone(self.parser.detect_language("Makefile"))

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    def test_parse_regex_python_valid(self):
        result = self.parser.parse("x = 1\n", "python")
        self.assertFalse(result.tree_available)
        self.assertEqual(result.language, "python")
        self.assertEqual(result.errors, [])
        self.assertGreater(result.node_count, 0)

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    def test_parse_regex_python_syntax_error(self):
        result = self.parser.parse("def foo(\n", "python")
        self.assertFalse(result.tree_available)
        self.assertTrue(len(result.errors) > 0)
        self.assertIn("SyntaxError", result.errors[0])

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    def test_parse_regex_non_python(self):
        result = self.parser.parse("function foo() {}\n", "javascript")
        self.assertFalse(result.tree_available)
        self.assertEqual(result.errors, [])

    def test_extension_map_has_20_plus_languages(self):
        languages = set(_EXTENSION_MAP.values())
        self.assertGreaterEqual(len(languages), 20)

    def test_detect_language_bash(self):
        self.assertEqual(self.parser.detect_language("script.sh"), "bash")

    def test_detect_language_kotlin(self):
        self.assertEqual(self.parser.detect_language("App.kt"), "kotlin")

    def test_detect_language_swift(self):
        self.assertEqual(self.parser.detect_language("main.swift"), "swift")

    def test_detect_language_php(self):
        self.assertEqual(self.parser.detect_language("index.php"), "php")


class TestTreeSitterParserWithTS(unittest.TestCase):
    """Tests with tree-sitter mocked as available."""

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", True)
    def test_is_available_true(self):
        parser = TreeSitterParser()
        self.assertTrue(parser.is_available())

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", True)
    def test_supported_languages_nonempty(self):
        parser = TreeSitterParser()
        langs = parser.supported_languages()
        self.assertIn("python", langs)
        self.assertIn("javascript", langs)

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", True)
    @patch("lidco.ast.treesitter_parser.get_parser")
    def test_parse_treesitter_success(self, mock_get_parser):
        root = MagicMock()
        root.type = "module"
        root.children = []
        root.start_point = (0, 0)
        tree = MagicMock()
        tree.root_node = root
        mock_parser = MagicMock()
        mock_parser.parse.return_value = tree
        mock_get_parser.return_value = mock_parser

        parser = TreeSitterParser()
        result = parser.parse("x = 1", "python")
        self.assertTrue(result.tree_available)
        self.assertEqual(result.language, "python")
        self.assertEqual(result.node_count, 1)
        self.assertEqual(result.errors, [])

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", True)
    @patch("lidco.ast.treesitter_parser.get_parser")
    def test_parse_treesitter_with_error_node(self, mock_get_parser):
        err_node = MagicMock()
        err_node.type = "ERROR"
        err_node.children = []
        err_node.start_point = (2, 5)
        root = MagicMock()
        root.type = "module"
        root.children = [err_node]
        root.start_point = (0, 0)
        tree = MagicMock()
        tree.root_node = root
        mock_parser = MagicMock()
        mock_parser.parse.return_value = tree
        mock_get_parser.return_value = mock_parser

        parser = TreeSitterParser()
        result = parser.parse("bad code", "python")
        self.assertTrue(result.tree_available)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("line 3", result.errors[0])

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", True)
    @patch("lidco.ast.treesitter_parser.get_parser", side_effect=RuntimeError("boom"))
    def test_parse_treesitter_exception_fallback(self, mock_get_parser):
        parser = TreeSitterParser()
        result = parser.parse("x = 1", "python")
        self.assertFalse(result.tree_available)
        self.assertIn("tree-sitter error", result.errors[0])


if __name__ == "__main__":
    unittest.main()
