"""Tests for PluginInstaller (Task 949)."""
from __future__ import annotations

import unittest

from lidco.marketplace.manifest import Capability, PluginManifest, TrustLevel
from lidco.marketplace.installer import InstalledPlugin, InstallScope, PluginInstaller


def _manifest(name="my-plugin", version="1.0.0"):
    return PluginManifest(
        name=name, version=version, description="desc", author="dev",
        trust_level=TrustLevel.COMMUNITY,
    )


class TestInstallScope(unittest.TestCase):
    def test_values(self):
        self.assertEqual(InstallScope.USER.value, "user")
        self.assertEqual(InstallScope.PROJECT.value, "project")


class TestInstalledPlugin(unittest.TestCase):
    def test_fields(self):
        m = _manifest()
        ip = InstalledPlugin(manifest=m, scope=InstallScope.PROJECT, installed_at=1.0, install_path="/x")
        self.assertTrue(ip.enabled)
        self.assertEqual(ip.scope, InstallScope.PROJECT)


class TestPluginInstallerInstall(unittest.TestCase):
    def setUp(self):
        self.written: dict[str, str] = {}
        self.deleted: list[str] = []
        self.installer = PluginInstaller(
            install_dir="/plugins",
            write_fn=lambda p, c: self.written.update({p: c}),
            read_fn=lambda p: self.written.get(p, ""),
            delete_fn=lambda p: self.deleted.append(p),
        )

    def test_install_returns_installed_plugin(self):
        ip = self.installer.install(_manifest())
        self.assertIsInstance(ip, InstalledPlugin)
        self.assertTrue(ip.enabled)
        self.assertIn("my-plugin", ip.install_path)

    def test_install_writes_manifest(self):
        self.installer.install(_manifest())
        self.assertTrue(len(self.written) > 0)

    def test_is_installed_after_install(self):
        self.assertFalse(self.installer.is_installed("my-plugin"))
        self.installer.install(_manifest())
        self.assertTrue(self.installer.is_installed("my-plugin"))

    def test_install_with_user_scope(self):
        ip = self.installer.install(_manifest(), scope=InstallScope.USER)
        self.assertEqual(ip.scope, InstallScope.USER)

    def test_list_installed(self):
        self.installer.install(_manifest("a"))
        self.installer.install(_manifest("b"))
        self.assertEqual(len(self.installer.list_installed()), 2)


class TestPluginInstallerUninstall(unittest.TestCase):
    def setUp(self):
        self.deleted: list[str] = []
        self.installer = PluginInstaller(
            write_fn=lambda p, c: None,
            read_fn=lambda p: "",
            delete_fn=lambda p: self.deleted.append(p),
        )

    def test_uninstall_existing(self):
        self.installer.install(_manifest())
        self.assertTrue(self.installer.uninstall("my-plugin"))
        self.assertFalse(self.installer.is_installed("my-plugin"))

    def test_uninstall_nonexistent(self):
        self.assertFalse(self.installer.uninstall("nope"))

    def test_uninstall_calls_delete(self):
        self.installer.install(_manifest())
        self.installer.uninstall("my-plugin")
        self.assertEqual(len(self.deleted), 1)


class TestPluginInstallerUpdate(unittest.TestCase):
    def setUp(self):
        self.installer = PluginInstaller(
            write_fn=lambda p, c: None,
            read_fn=lambda p: "",
            delete_fn=lambda p: None,
        )

    def test_update_returns_new_version(self):
        self.installer.install(_manifest("p", "1.0.0"))
        ip = self.installer.update("p", _manifest("p", "2.0.0"))
        self.assertEqual(ip.manifest.version, "2.0.0")

    def test_update_not_installed_raises(self):
        with self.assertRaises(KeyError):
            self.installer.update("missing", _manifest())


class TestPluginInstallerEnableDisable(unittest.TestCase):
    def setUp(self):
        self.installer = PluginInstaller(
            write_fn=lambda p, c: None,
            read_fn=lambda p: "",
            delete_fn=lambda p: None,
        )
        self.installer.install(_manifest())

    def test_disable(self):
        self.installer.disable("my-plugin")
        items = self.installer.list_installed()
        self.assertFalse(items[0].enabled)

    def test_enable_after_disable(self):
        self.installer.disable("my-plugin")
        self.installer.enable("my-plugin")
        items = self.installer.list_installed()
        self.assertTrue(items[0].enabled)

    def test_disable_not_installed_raises(self):
        with self.assertRaises(KeyError):
            self.installer.disable("nope")

    def test_enable_not_installed_raises(self):
        with self.assertRaises(KeyError):
            self.installer.enable("nope")


if __name__ == "__main__":
    unittest.main()
