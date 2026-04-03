"""Tests for Q253 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q253_cmds as q253_mod


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q253_mod.register(reg)
        self._commands = reg._commands


class TestGenTestsCmd(_CmdTestBase):
    def test_scaffold(self):
        handler = self._commands["gen-tests"].handler
        source = "class Calc:\n    def add(self):\n        pass\n"
        result = asyncio.run(handler(f"scaffold {source}"))
        self.assertIn("TestCalc", result)

    def test_functions(self):
        handler = self._commands["gen-tests"].handler
        source = "def hello():\n    pass\n"
        result = asyncio.run(handler(f"functions {source}"))
        self.assertIn("hello", result)

    def test_classes(self):
        handler = self._commands["gen-tests"].handler
        source = "class Foo:\n    def bar(self):\n        pass\n"
        result = asyncio.run(handler(f"classes {source}"))
        self.assertIn("Foo", result)

    def test_file(self):
        handler = self._commands["gen-tests"].handler
        source = "def greet():\n    pass\n"
        result = asyncio.run(handler(f"file mod.py {source}"))
        self.assertIn("mod.py", result)

    def test_usage(self):
        handler = self._commands["gen-tests"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_scaffold_empty(self):
        handler = self._commands["gen-tests"].handler
        result = asyncio.run(handler("scaffold"))
        self.assertIn("Usage", result)

    def test_functions_empty(self):
        handler = self._commands["gen-tests"].handler
        result = asyncio.run(handler("functions"))
        self.assertIn("Usage", result)

    def test_classes_empty(self):
        handler = self._commands["gen-tests"].handler
        result = asyncio.run(handler("classes"))
        self.assertIn("Usage", result)


class TestEdgeCasesCmd(_CmdTestBase):
    def test_type_int(self):
        handler = self._commands["edge-cases"].handler
        result = asyncio.run(handler("type int"))
        self.assertIn("Edge cases", result)
        self.assertIn("boundary", result)

    def test_type_unknown(self):
        handler = self._commands["edge-cases"].handler
        result = asyncio.run(handler("type unknown"))
        self.assertIn("No edge cases", result)

    def test_boundary(self):
        handler = self._commands["edge-cases"].handler
        result = asyncio.run(handler("boundary 0 100"))
        self.assertIn("Boundary values", result)

    def test_categories(self):
        handler = self._commands["edge-cases"].handler
        result = asyncio.run(handler("categories"))
        self.assertIn("Categories", result)
        self.assertIn("boundary", result)

    def test_usage(self):
        handler = self._commands["edge-cases"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_type_empty(self):
        handler = self._commands["edge-cases"].handler
        result = asyncio.run(handler("type"))
        self.assertIn("Usage", result)

    def test_boundary_missing_args(self):
        handler = self._commands["edge-cases"].handler
        result = asyncio.run(handler("boundary 5"))
        self.assertIn("Usage", result)


class TestGenMocksCmd(_CmdTestBase):
    def test_generate(self):
        handler = self._commands["gen-mocks"].handler
        result = asyncio.run(handler("generate MyService"))
        self.assertIn("MockMyService", result)

    def test_spy(self):
        handler = self._commands["gen-mocks"].handler
        result = asyncio.run(handler("spy MyService"))
        self.assertIn("SpyMyService", result)

    def test_from_source(self):
        handler = self._commands["gen-mocks"].handler
        source = "class Repo:\n    def find(self, id):\n        pass\n"
        result = asyncio.run(handler(f"from Repo {source}"))
        self.assertIn("MockRepo", result)

    def test_usage(self):
        handler = self._commands["gen-mocks"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_generate_empty(self):
        handler = self._commands["gen-mocks"].handler
        result = asyncio.run(handler("generate"))
        self.assertIn("Usage", result)


class TestTestDataCmd(_CmdTestBase):
    def test_string(self):
        handler = self._commands["test-data"].handler
        result = asyncio.run(handler("string 5"))
        self.assertEqual(len(result), 5)

    def test_string_default(self):
        handler = self._commands["test-data"].handler
        result = asyncio.run(handler("string"))
        self.assertEqual(len(result), 10)

    def test_int(self):
        handler = self._commands["test-data"].handler
        result = asyncio.run(handler("int 0 100"))
        val = int(result)
        self.assertGreaterEqual(val, 0)
        self.assertLessEqual(val, 100)

    def test_int_default(self):
        handler = self._commands["test-data"].handler
        result = asyncio.run(handler("int"))
        val = int(result)
        self.assertGreaterEqual(val, 0)
        self.assertLessEqual(val, 1000)

    def test_email(self):
        handler = self._commands["test-data"].handler
        result = asyncio.run(handler("email"))
        self.assertIn("@", result)

    def test_usage(self):
        handler = self._commands["test-data"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
