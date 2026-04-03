"""Tests for Q257 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q257_cmds as q257_mod


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.registry import CommandRegistry

        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q257_mod.register(reg)
        self._commands = reg._commands


class TestInferTypesCmd(_CmdTestBase):
    def test_infer_int(self):
        handler = self._commands["infer-types"].handler
        result = asyncio.run(handler("x = 5"))
        self.assertIn("int", result)
        self.assertIn("x", result)

    def test_empty_input(self):
        handler = self._commands["infer-types"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_no_inference(self):
        handler = self._commands["infer-types"].handler
        result = asyncio.run(handler("import os"))
        self.assertIn("No types", result)


class TestAnnotateTypesCmd(_CmdTestBase):
    def test_annotate_assignment(self):
        handler = self._commands["annotate-types"].handler
        result = asyncio.run(handler("x = 5"))
        # Should show diff or no-change message.
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_empty_input(self):
        handler = self._commands["annotate-types"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


class TestTypeCheckCmd(_CmdTestBase):
    def test_parse_mypy(self):
        handler = self._commands["type-check"].handler
        mypy_out = "foo.py:10: error: Incompatible return value type [return-value]"
        result = asyncio.run(handler(mypy_out))
        self.assertIn("1 issue", result)
        self.assertIn("foo.py", result)

    def test_parse_pyright(self):
        handler = self._commands["type-check"].handler
        pyright_out = 'bar.py:5:1 - error: Cannot assign type "str" to "int" (reportAssignment)'
        result = asyncio.run(handler(pyright_out))
        self.assertIn("1 issue", result)
        self.assertIn("bar.py", result)

    def test_empty_input(self):
        handler = self._commands["type-check"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_no_errors_parsed(self):
        handler = self._commands["type-check"].handler
        result = asyncio.run(handler("all good"))
        self.assertIn("No type errors", result)


class TestMigrateTypesCmd(_CmdTestBase):
    def test_apply(self):
        handler = self._commands["migrate-types"].handler
        result = asyncio.run(handler("apply x: Optional[int] = None"))
        self.assertIn("int | None", result)

    def test_apply_no_change(self):
        handler = self._commands["migrate-types"].handler
        result = asyncio.run(handler("apply x: int = 5"))
        self.assertIn("No migrations", result)

    def test_preview(self):
        handler = self._commands["migrate-types"].handler
        result = asyncio.run(handler("preview x: List[int] = []"))
        self.assertIn("rule", result.lower())

    def test_preview_no_change(self):
        handler = self._commands["migrate-types"].handler
        result = asyncio.run(handler("preview x: int = 5"))
        self.assertIn("No migrations", result)

    def test_rules(self):
        handler = self._commands["migrate-types"].handler
        result = asyncio.run(handler("rules"))
        self.assertIn("rule", result.lower())
        self.assertIn("PEP", result)

    def test_usage(self):
        handler = self._commands["migrate-types"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_apply_empty(self):
        handler = self._commands["migrate-types"].handler
        result = asyncio.run(handler("apply"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
