"""Tests for Q250 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q250_cmds as q250_mod


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q250_mod.register(reg)
        self._commands = reg._commands


class TestDetectLangCmd(_CmdTestBase):
    def test_file(self):
        handler = self._commands["detect-lang"].handler
        result = asyncio.run(handler("file main.py"))
        self.assertIn("python", result)
        self.assertIn("extension", result)

    def test_content(self):
        handler = self._commands["detect-lang"].handler
        result = asyncio.run(handler("content def foo(): pass"))
        self.assertIn("python", result)

    def test_languages(self):
        handler = self._commands["detect-lang"].handler
        result = asyncio.run(handler("languages"))
        self.assertIn("python", result)
        self.assertIn("javascript", result)

    def test_usage(self):
        handler = self._commands["detect-lang"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_file_empty_arg(self):
        handler = self._commands["detect-lang"].handler
        result = asyncio.run(handler("file"))
        self.assertIn("Usage", result)

    def test_content_empty_arg(self):
        handler = self._commands["detect-lang"].handler
        result = asyncio.run(handler("content"))
        self.assertIn("Usage", result)


class TestParseUniversalCmd(_CmdTestBase):
    def test_parse(self):
        handler = self._commands["parse-universal"].handler
        result = asyncio.run(handler("parse python def foo(): pass"))
        self.assertIn("foo", result)
        self.assertIn("symbol", result.lower())

    def test_parse_no_symbols(self):
        handler = self._commands["parse-universal"].handler
        result = asyncio.run(handler("parse python # just a comment"))
        self.assertIn("No symbols", result)

    def test_imports(self):
        handler = self._commands["parse-universal"].handler
        result = asyncio.run(handler("imports python import os"))
        self.assertIn("os", result)

    def test_imports_none(self):
        handler = self._commands["parse-universal"].handler
        result = asyncio.run(handler("imports python x = 1"))
        self.assertIn("No imports", result)

    def test_usage(self):
        handler = self._commands["parse-universal"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_parse_empty_arg(self):
        handler = self._commands["parse-universal"].handler
        result = asyncio.run(handler("parse"))
        self.assertIn("Usage", result)

    def test_imports_empty_arg(self):
        handler = self._commands["parse-universal"].handler
        result = asyncio.run(handler("imports"))
        self.assertIn("Usage", result)


class TestCrossLinkCmd(_CmdTestBase):
    def test_demo(self):
        handler = self._commands["cross-link"].handler
        result = asyncio.run(handler("demo"))
        self.assertIn("cross-language", result.lower())
        self.assertIn("process", result)

    def test_summary_empty(self):
        handler = self._commands["cross-link"].handler
        result = asyncio.run(handler("summary"))
        self.assertIn("No cross-language links", result)

    def test_usage(self):
        handler = self._commands["cross-link"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestPolyglotSearchCmd(_CmdTestBase):
    def test_normalize(self):
        handler = self._commands["polyglot-search"].handler
        result = asyncio.run(handler("normalize getUserName"))
        self.assertIn("getusername", result)

    def test_normalize_empty(self):
        handler = self._commands["polyglot-search"].handler
        result = asyncio.run(handler("normalize"))
        self.assertIn("Usage", result)

    def test_stats_empty(self):
        handler = self._commands["polyglot-search"].handler
        result = asyncio.run(handler("stats"))
        self.assertIn("No symbols", result)

    def test_usage(self):
        handler = self._commands["polyglot-search"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestRegistration(_CmdTestBase):
    def test_all_commands_registered(self):
        expected = {"detect-lang", "parse-universal", "cross-link", "polyglot-search"}
        self.assertEqual(set(self._commands.keys()), expected)

    def test_descriptions(self):
        for cmd in self._commands.values():
            self.assertTrue(len(cmd.description) > 0)


if __name__ == "__main__":
    unittest.main()
