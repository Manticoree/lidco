"""Tests for Q184 CLI commands (Task 1036)."""
from __future__ import annotations

import asyncio
import unittest

from lidco.marketplace.manifest2 import (
    AuthorInfo,
    PluginCategory,
    PluginManifest2,
)
from lidco.marketplace.registry2 import MarketplaceRegistry
from lidco.marketplace.installer2 import PluginInstaller2

import lidco.cli.commands.q184_cmds as q184_mod


def _make(name="test-plug", category=PluginCategory.DEVELOPMENT) -> PluginManifest2:
    return PluginManifest2(
        name=name,
        version="1.0.0",
        description="A test plugin",
        author=AuthorInfo(name="dev"),
        category=category,
    )


def _setup_state():
    """Inject shared objects into module state for CLI handlers."""
    q184_mod._state.clear()
    reg = MarketplaceRegistry()
    reg.register(_make("alpha", PluginCategory.DEVELOPMENT))
    reg.register(_make("beta", PluginCategory.SECURITY))
    installer = PluginInstaller2(
        write_fn=lambda p, c: None,
        read_fn=lambda p: "",
        delete_fn=lambda p: None,
    )
    q184_mod._state["registry"] = reg
    q184_mod._state["installer"] = installer
    return reg, installer


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        self.reg, self.installer = _setup_state()
        from lidco.cli.commands.registry import CommandRegistry
        cr = CommandRegistry.__new__(CommandRegistry)
        cr._commands = {}
        cr._session = None
        q184_mod.register(cr)
        self.marketplace2 = cr._commands["marketplace2"].handler
        self.search = cr._commands["marketplace2-search"].handler
        self.install_cmd = cr._commands["marketplace2-install"].handler
        self.uninstall_cmd = cr._commands["marketplace2-uninstall"].handler


# ------------------------------------------------------------------
# /marketplace2
# ------------------------------------------------------------------

class TestMarketplace2List(_CmdTestBase):
    def test_list_plugins(self):
        result = asyncio.run(self.marketplace2("list"))
        self.assertIn("alpha", result)
        self.assertIn("beta", result)
        self.assertIn("2 plugin(s)", result)

    def test_list_empty(self):
        q184_mod._state["registry"] = MarketplaceRegistry()
        result = asyncio.run(self.marketplace2("list"))
        self.assertIn("No plugins", result)


class TestMarketplace2Info(_CmdTestBase):
    def test_info_found(self):
        result = asyncio.run(self.marketplace2("info alpha"))
        self.assertIn("alpha", result)
        self.assertIn("1.0.0", result)

    def test_info_not_found(self):
        result = asyncio.run(self.marketplace2("info nope"))
        self.assertIn("not found", result)

    def test_info_no_args(self):
        result = asyncio.run(self.marketplace2("info"))
        self.assertIn("Usage", result)


class TestMarketplace2Categories(_CmdTestBase):
    def test_categories(self):
        result = asyncio.run(self.marketplace2("categories"))
        self.assertIn("development", result)
        self.assertIn("security", result)

    def test_categories_empty(self):
        q184_mod._state["registry"] = MarketplaceRegistry()
        result = asyncio.run(self.marketplace2("categories"))
        self.assertIn("No categories", result)


class TestMarketplace2Help(_CmdTestBase):
    def test_help(self):
        result = asyncio.run(self.marketplace2(""))
        self.assertIn("Usage", result)

    def test_unknown_sub(self):
        result = asyncio.run(self.marketplace2("unknown"))
        self.assertIn("Usage", result)


# ------------------------------------------------------------------
# /marketplace2-search
# ------------------------------------------------------------------

class TestMarketplace2Search(_CmdTestBase):
    def test_search_found(self):
        result = asyncio.run(self.search("alpha"))
        self.assertIn("alpha", result)
        self.assertIn("1 plugin(s)", result)

    def test_search_not_found(self):
        result = asyncio.run(self.search("zzz"))
        self.assertIn("No plugins found", result)

    def test_search_no_args(self):
        result = asyncio.run(self.search(""))
        self.assertIn("Usage", result)


# ------------------------------------------------------------------
# /marketplace2-install
# ------------------------------------------------------------------

class TestMarketplace2Install(_CmdTestBase):
    def test_install_success(self):
        result = asyncio.run(self.install_cmd("alpha"))
        self.assertIn("Installed", result)
        self.assertIn("alpha", result)

    def test_install_not_found(self):
        result = asyncio.run(self.install_cmd("nope"))
        self.assertIn("not found", result)

    def test_install_no_args(self):
        result = asyncio.run(self.install_cmd(""))
        self.assertIn("Usage", result)

    def test_install_already_installed(self):
        asyncio.run(self.install_cmd("alpha"))
        result = asyncio.run(self.install_cmd("alpha"))
        self.assertIn("already installed", result)


# ------------------------------------------------------------------
# /marketplace2-uninstall
# ------------------------------------------------------------------

class TestMarketplace2Uninstall(_CmdTestBase):
    def test_uninstall_success(self):
        asyncio.run(self.install_cmd("alpha"))
        result = asyncio.run(self.uninstall_cmd("alpha"))
        self.assertIn("Uninstalled", result)

    def test_uninstall_not_installed(self):
        result = asyncio.run(self.uninstall_cmd("nope"))
        self.assertIn("not installed", result)

    def test_uninstall_no_args(self):
        result = asyncio.run(self.uninstall_cmd(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
