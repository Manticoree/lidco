"""Tests for Q264 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q264_cmds as q264_mod
from lidco.cli.commands.registry import CommandRegistry, SlashCommand


def _registry() -> CommandRegistry:
    reg = CommandRegistry.__new__(CommandRegistry)
    reg._commands = {}
    reg._session = None
    q264_mod._state.clear()
    q264_mod.register(reg)
    return reg


class TestTenantCmd(unittest.TestCase):
    def setUp(self):
        reg = _registry()
        self.handler = reg._commands["tenant"].handler

    def test_no_args(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_create(self):
        result = asyncio.run(self.handler("create acme"))
        self.assertIn("Created", result)

    def test_list_empty(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("No tenants", result)

    def test_create_and_list(self):
        asyncio.run(self.handler("create acme"))
        result = asyncio.run(self.handler("list"))
        self.assertIn("acme", result)

    def test_delete_missing(self):
        result = asyncio.run(self.handler("delete nope"))
        self.assertIn("not found", result)


class TestTenantQuotaCmd(unittest.TestCase):
    def setUp(self):
        reg = _registry()
        self.handler = reg._commands["tenant-quota"].handler

    def test_no_args(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_set_and_check(self):
        result = asyncio.run(self.handler("set t1 tokens 80 100"))
        self.assertIn("Quota set", result)
        result = asyncio.run(self.handler("check t1 tokens 50"))
        self.assertIn("allowed", result)


class TestTenantStatsCmd(unittest.TestCase):
    def setUp(self):
        reg = _registry()
        self.handler = reg._commands["tenant-stats"].handler

    def test_no_args_summary(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("total_records", result)


class TestTenantConfigCmd(unittest.TestCase):
    def setUp(self):
        reg = _registry()
        self.tenant_handler = reg._commands["tenant"].handler
        self.config_handler = reg._commands["tenant-config"].handler

    def test_no_args(self):
        result = asyncio.run(self.config_handler(""))
        self.assertIn("Usage", result)

    def test_missing_tenant(self):
        result = asyncio.run(self.config_handler("nope"))
        self.assertIn("No config", result)


if __name__ == "__main__":
    unittest.main()
