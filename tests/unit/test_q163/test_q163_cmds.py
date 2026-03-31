"""Tests for Q163 CLI commands."""
from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from lidco.cli.commands import q163_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ163Commands(unittest.TestCase):
    def setUp(self):
        q163_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q163_cmds.register(MockRegistry())

    def test_ast_registered(self):
        self.assertIn("ast", self.registered)

    def test_repomap_registered(self):
        self.assertIn("repomap", self.registered)

    def test_ast_lint_registered(self):
        self.assertIn("ast-lint", self.registered)

    # --- /ast ---

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_ast_no_args(self):
        result = _run(self.registered["ast"].handler(""))
        self.assertIn("Usage", result)

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_ast_parse_missing_file(self):
        result = _run(self.registered["ast"].handler("parse"))
        self.assertIn("Usage", result)

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_ast_parse_unknown_ext(self):
        result = _run(self.registered["ast"].handler("parse readme.txt"))
        self.assertIn("Cannot detect", result)

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    @patch("lidco.ast.universal_extractor.HAS_TREESITTER", False)
    def test_ast_parse_real_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def hello():\n    pass\n")
            f.flush()
            path = f.name
        try:
            result = _run(self.registered["ast"].handler(f"parse {path}"))
            self.assertIn("Language: python", result)
            self.assertIn("Symbols:", result)
            self.assertIn("hello", result)
        finally:
            os.unlink(path)

    # --- /ast-lint ---

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_ast_lint_no_args(self):
        result = _run(self.registered["ast-lint"].handler(""))
        self.assertIn("Usage", result)

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_ast_lint_valid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = f.name
        try:
            result = _run(self.registered["ast-lint"].handler(path))
            self.assertIn("Valid: yes", result)
        finally:
            os.unlink(path)

    @patch("lidco.ast.treesitter_parser.HAS_TREESITTER", False)
    @patch("lidco.ast.ast_linter.HAS_TREESITTER", False)
    def test_ast_lint_invalid_file(self):
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def foo(\n")
            f.flush()
            path = f.name
        try:
            result = _run(self.registered["ast-lint"].handler(path))
            self.assertIn("Valid: NO", result)
            self.assertIn("Errors", result)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
