"""Tests for Q256 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import CommandRegistry, SlashCommand
from lidco.cli.commands.q256_cmds import register


def _run(coro):
    return asyncio.run(coro)


class TestQ256Registration(unittest.TestCase):
    def setUp(self):
        self.registry = CommandRegistry()
        register(self.registry)

    def test_api_extract_registered(self):
        self.assertIn("api-extract", self.registry._commands)

    def test_api_diff_registered(self):
        self.assertIn("api-diff", self.registry._commands)

    def test_api_mock_registered(self):
        self.assertIn("api-mock", self.registry._commands)

    def test_api_test_registered(self):
        self.assertIn("api-test", self.registry._commands)


SAMPLE_SOURCE = '@app.get("/users")\ndef list_users(skip: int):\n    """List users."""\n    pass'


class TestApiExtractCommand(unittest.TestCase):
    def setUp(self):
        self.registry = CommandRegistry()
        register(self.registry)
        self.handler = self.registry._commands["api-extract"].handler

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_source_no_code(self):
        result = _run(self.handler("source"))
        self.assertIn("Usage", result)

    def test_source_with_code(self):
        result = _run(self.handler(f"source {SAMPLE_SOURCE}"))
        self.assertIn("endpoint", result.lower())

    def test_openapi(self):
        result = _run(self.handler(f"openapi {SAMPLE_SOURCE}"))
        self.assertIn("openapi", result.lower())

    def test_graphql(self):
        result = _run(self.handler(f"graphql {SAMPLE_SOURCE}"))
        self.assertIn("Query", result)


class TestApiDiffCommand(unittest.TestCase):
    def setUp(self):
        self.registry = CommandRegistry()
        register(self.registry)
        self.handler = self.registry._commands["api-diff"].handler

    def test_no_separator(self):
        result = _run(self.handler("some code"))
        self.assertIn("Usage", result)

    def test_no_changes(self):
        result = _run(self.handler(f"{SAMPLE_SOURCE} ||| {SAMPLE_SOURCE}"))
        self.assertIn("No API changes", result)

    def test_with_changes(self):
        old = '@app.get("/a")\ndef a():\n    pass'
        new = '@app.get("/b")\ndef b():\n    pass'
        result = _run(self.handler(f"{old} ||| {new}"))
        self.assertIn("change", result.lower())


class TestApiMockCommand(unittest.TestCase):
    def setUp(self):
        self.registry = CommandRegistry()
        register(self.registry)
        self.handler = self.registry._commands["api-mock"].handler

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_generate_no_code(self):
        result = _run(self.handler("generate"))
        self.assertIn("Usage", result)

    def test_generate_with_code(self):
        result = _run(self.handler(f"generate {SAMPLE_SOURCE}"))
        self.assertIn("route", result.lower())

    def test_test_no_args(self):
        result = _run(self.handler("test"))
        self.assertIn("Usage", result)

    def test_test_missing_path(self):
        result = _run(self.handler("test GET"))
        self.assertIn("Usage", result)


class TestApiTestCommand(unittest.TestCase):
    def setUp(self):
        self.registry = CommandRegistry()
        register(self.registry)
        self.handler = self.registry._commands["api-test"].handler

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_generate(self):
        result = _run(self.handler(f"generate {SAMPLE_SOURCE}"))
        self.assertIn("test case", result.lower())

    def test_python(self):
        result = _run(self.handler(f"python {SAMPLE_SOURCE}"))
        self.assertIn("class TestAPI", result)

    def test_generate_no_code(self):
        result = _run(self.handler("generate"))
        self.assertIn("Usage", result)

    def test_python_no_code(self):
        result = _run(self.handler("python"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
