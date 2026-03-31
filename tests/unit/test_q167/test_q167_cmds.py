"""Tests for Q167 CLI commands (Task 951)."""
from __future__ import annotations

import asyncio
import unittest

from lidco.marketplace.manifest import PluginManifest, TrustLevel, Capability
from lidco.marketplace.discovery import PluginDiscovery
from lidco.marketplace.installer import PluginInstaller
from lidco.marketplace.trust_gate import TrustGate

# Reset shared state between tests
import lidco.cli.commands.q167_cmds as q167_mod


def _make_plugin(name="test-plug", trust=TrustLevel.VERIFIED):
    return PluginManifest(
        name=name, version="1.0.0", description="A test plugin", author="dev",
        trust_level=trust, category="tools",
    )


def _setup_state():
    """Inject shared objects into module state for CLI handlers."""
    q167_mod._state.clear()
    discovery = PluginDiscovery()
    discovery.add_plugin(_make_plugin("alpha"))
    discovery.add_plugin(_make_plugin("beta", TrustLevel.COMMUNITY))
    installer = PluginInstaller(
        write_fn=lambda p, c: None,
        read_fn=lambda p: "",
        delete_fn=lambda p: None,
    )
    gate = TrustGate()
    q167_mod._state["discovery"] = discovery
    q167_mod._state["installer"] = installer
    q167_mod._state["gate"] = gate
    return discovery, installer, gate


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        self.discovery, self.installer, self.gate = _setup_state()
        # Get the handler via registry
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q167_mod.register(reg)
        self.marketplace = reg._commands["marketplace"].handler
        self.trust = reg._commands["trust"].handler


class TestMarketplaceSearch(_CmdTestBase):
    def test_search_found(self):
        result = asyncio.run(self.marketplace("search alpha"))
        self.assertIn("alpha", result)
        self.assertIn("1 plugin", result)

    def test_search_no_query(self):
        result = asyncio.run(self.marketplace("search"))
        self.assertIn("Usage", result)

    def test_search_not_found(self):
        result = asyncio.run(self.marketplace("search zzz"))
        self.assertIn("No plugins", result)


class TestMarketplaceBrowse(_CmdTestBase):
    def test_browse_all(self):
        result = asyncio.run(self.marketplace("browse"))
        self.assertIn("alpha", result)
        self.assertIn("beta", result)

    def test_browse_category(self):
        result = asyncio.run(self.marketplace("browse tools"))
        self.assertIn("alpha", result)

    def test_browse_empty_category(self):
        result = asyncio.run(self.marketplace("browse nonexistent"))
        self.assertIn("No plugins", result)


class TestMarketplaceInfo(_CmdTestBase):
    def test_info_found(self):
        result = asyncio.run(self.marketplace("info alpha"))
        self.assertIn("alpha", result)
        self.assertIn("1.0.0", result)

    def test_info_not_found(self):
        result = asyncio.run(self.marketplace("info nope"))
        self.assertIn("not found", result)

    def test_info_no_args(self):
        result = asyncio.run(self.marketplace("info"))
        self.assertIn("Usage", result)


class TestMarketplaceInstall(_CmdTestBase):
    def test_install_verified(self):
        result = asyncio.run(self.marketplace("install alpha"))
        self.assertIn("Installed", result)

    def test_install_not_found(self):
        result = asyncio.run(self.marketplace("install nope"))
        self.assertIn("not found", result)

    def test_install_no_args(self):
        result = asyncio.run(self.marketplace("install"))
        self.assertIn("Usage", result)

    def test_install_blocked_unverified(self):
        self.discovery.add_plugin(_make_plugin("shady", TrustLevel.UNVERIFIED))
        result = asyncio.run(self.marketplace("install shady"))
        self.assertIn("blocked", result.lower())


class TestMarketplaceUninstall(_CmdTestBase):
    def test_uninstall_installed(self):
        asyncio.run(self.marketplace("install alpha"))
        result = asyncio.run(self.marketplace("uninstall alpha"))
        self.assertIn("Uninstalled", result)

    def test_uninstall_not_installed(self):
        result = asyncio.run(self.marketplace("uninstall nope"))
        self.assertIn("not installed", result)


class TestMarketplaceList(_CmdTestBase):
    def test_list_empty(self):
        result = asyncio.run(self.marketplace("list"))
        self.assertIn("No plugins", result)

    def test_list_after_install(self):
        asyncio.run(self.marketplace("install alpha"))
        result = asyncio.run(self.marketplace("list"))
        self.assertIn("alpha", result)
        self.assertIn("1 installed", result)


class TestMarketplaceHelp(_CmdTestBase):
    def test_help(self):
        result = asyncio.run(self.marketplace(""))
        self.assertIn("Usage", result)


class TestTrustCommand(_CmdTestBase):
    def test_trust_show(self):
        result = asyncio.run(self.trust("show myplugin"))
        self.assertIn("Allowed: False", result)

    def test_trust_set_allow(self):
        result = asyncio.run(self.trust("set myplugin allow"))
        self.assertIn("allowlist", result.lower())
        result2 = asyncio.run(self.trust("show myplugin"))
        self.assertIn("True", result2)

    def test_trust_set_deny(self):
        asyncio.run(self.trust("set myplugin allow"))
        result = asyncio.run(self.trust("set myplugin deny"))
        self.assertIn("Removed", result)

    def test_trust_help(self):
        result = asyncio.run(self.trust(""))
        self.assertIn("Usage", result)

    def test_trust_show_no_name(self):
        result = asyncio.run(self.trust("show"))
        self.assertIn("Usage", result)

    def test_trust_set_bad_action(self):
        result = asyncio.run(self.trust("set plug badaction"))
        self.assertIn("Unknown", result)


if __name__ == "__main__":
    unittest.main()
