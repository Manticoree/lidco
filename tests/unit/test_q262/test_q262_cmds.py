"""Tests for Q262 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q262_cmds as q262_mod
from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def _registry() -> CommandRegistry:
    reg = CommandRegistry.__new__(CommandRegistry)
    reg._commands = {}
    reg._session = None
    q262_mod._state.clear()
    q262_mod.register(reg)
    return reg


class TestScanSecretsCmd(unittest.TestCase):
    def setUp(self):
        reg = _registry()
        self.handler = reg._commands["scan-secrets"].handler

    def test_no_args(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_clean_text(self):
        result = asyncio.run(self.handler("hello world nothing here"))
        self.assertIn("No secrets found", result)

    def test_detects_aws_key(self):
        result = asyncio.run(self.handler("key=AKIAIOSFODNN7EXAMPLE"))
        self.assertIn("aws_access_key", result)


class TestRotateSecretCmd(unittest.TestCase):
    def setUp(self):
        reg = _registry()
        self.handler = reg._commands["rotate-secret"].handler

    def test_no_args(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_no_handler(self):
        result = asyncio.run(self.handler("mykey aws old_value_1234"))
        self.assertIn("failed", result)


class TestVaultCmd(unittest.TestCase):
    def setUp(self):
        reg = _registry()
        self.handler = reg._commands["vault"].handler

    def test_put_and_get(self):
        result = asyncio.run(self.handler("put mykey myvalue"))
        self.assertIn("Stored", result)
        result = asyncio.run(self.handler("get mykey"))
        self.assertIn("myvalue", result)

    def test_list(self):
        asyncio.run(self.handler("put a 1"))
        result = asyncio.run(self.handler("list"))
        self.assertIn("a", result)

    def test_delete(self):
        asyncio.run(self.handler("put x 1"))
        result = asyncio.run(self.handler("delete x"))
        self.assertIn("Deleted", result)

    def test_summary(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Vault", result)


class TestSecretInventoryCmd(unittest.TestCase):
    def setUp(self):
        reg = _registry()
        self.handler = reg._commands["secret-inventory"].handler

    def test_add_and_list(self):
        result = asyncio.run(self.handler("add db-pass"))
        self.assertIn("Added", result)
        result = asyncio.run(self.handler("list"))
        self.assertIn("db-pass", result)

    def test_empty_list(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("empty", result)

    def test_summary_default(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("total", result)


if __name__ == "__main__":
    unittest.main()
