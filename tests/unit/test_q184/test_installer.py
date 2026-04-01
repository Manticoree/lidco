"""Tests for PluginInstaller2 (Task 1034)."""
from __future__ import annotations

import json
import unittest

from lidco.marketplace.manifest2 import (
    AuthorInfo,
    PluginCategory,
    PluginManifest2,
)
from lidco.marketplace.installer2 import InstalledPlugin2, PluginInstaller2


def _make(name="my-plugin", version="1.0.0") -> PluginManifest2:
    return PluginManifest2(
        name=name,
        version=version,
        description="desc",
        author=AuthorInfo(name="dev"),
        category=PluginCategory.DEVELOPMENT,
    )


class _InstallerTestBase(unittest.TestCase):
    def setUp(self):
        self.written: dict[str, str] = {}
        self.deleted: list[str] = []
        self.installer = PluginInstaller2(
            target_dir="/plugins",
            write_fn=lambda p, c: self.written.update({p: c}),
            read_fn=lambda p: self.written.get(p, ""),
            delete_fn=lambda p: self.deleted.append(p),
            exists_fn=lambda p: p in self.written,
        )


# ------------------------------------------------------------------
# InstalledPlugin2
# ------------------------------------------------------------------

class TestInstalledPlugin2(unittest.TestCase):
    def test_fields(self):
        m = _make()
        ip = InstalledPlugin2(
            name="my-plugin", version="1.0.0", path="/x",
            installed_at=1.0, manifest=m, checksum="abc",
        )
        self.assertEqual(ip.name, "my-plugin")
        self.assertEqual(ip.checksum, "abc")

    def test_frozen(self):
        m = _make()
        ip = InstalledPlugin2(name="p", version="1.0.0", path="/x", installed_at=1.0, manifest=m)
        with self.assertRaises(AttributeError):
            ip.name = "q"  # type: ignore[misc]

    def test_default_checksum(self):
        m = _make()
        ip = InstalledPlugin2(name="p", version="1.0.0", path="/x", installed_at=1.0, manifest=m)
        self.assertEqual(ip.checksum, "")


# ------------------------------------------------------------------
# Install
# ------------------------------------------------------------------

class TestPluginInstaller2Install(_InstallerTestBase):
    def test_install_returns_installed_plugin(self):
        ip = self.installer.install(_make())
        self.assertIsInstance(ip, InstalledPlugin2)
        self.assertEqual(ip.name, "my-plugin")

    def test_install_writes_manifest(self):
        self.installer.install(_make())
        self.assertTrue(len(self.written) > 0)
        path = list(self.written.keys())[0]
        self.assertIn("my-plugin", path)

    def test_install_sets_checksum(self):
        ip = self.installer.install(_make())
        self.assertNotEqual(ip.checksum, "")

    def test_is_installed_after_install(self):
        self.assertFalse(self.installer.is_installed("my-plugin"))
        self.installer.install(_make())
        self.assertTrue(self.installer.is_installed("my-plugin"))

    def test_get_installed(self):
        self.installer.install(_make())
        ip = self.installer.get_installed("my-plugin")
        self.assertIsNotNone(ip)
        self.assertEqual(ip.version, "1.0.0")

    def test_get_installed_missing(self):
        self.assertIsNone(self.installer.get_installed("nope"))

    def test_list_installed(self):
        self.installer.install(_make("a"))
        self.installer.install(_make("b"))
        self.assertEqual(len(self.installer.list_installed()), 2)


# ------------------------------------------------------------------
# Uninstall
# ------------------------------------------------------------------

class TestPluginInstaller2Uninstall(_InstallerTestBase):
    def test_uninstall_existing(self):
        self.installer.install(_make())
        self.assertTrue(self.installer.uninstall("my-plugin"))
        self.assertFalse(self.installer.is_installed("my-plugin"))

    def test_uninstall_nonexistent(self):
        self.assertFalse(self.installer.uninstall("nope"))

    def test_uninstall_calls_delete(self):
        self.installer.install(_make())
        self.installer.uninstall("my-plugin")
        self.assertEqual(len(self.deleted), 1)

    def test_uninstall_removes_from_list(self):
        self.installer.install(_make())
        self.installer.uninstall("my-plugin")
        self.assertEqual(len(self.installer.list_installed()), 0)


# ------------------------------------------------------------------
# Update
# ------------------------------------------------------------------

class TestPluginInstaller2Update(_InstallerTestBase):
    def test_update_with_new_manifest(self):
        self.installer.install(_make("p", "1.0.0"))
        ip = self.installer.update("p", _make("p", "2.0.0"))
        self.assertEqual(ip.version, "2.0.0")

    def test_update_without_new_manifest(self):
        self.installer.install(_make("p", "1.0.0"))
        ip = self.installer.update("p")
        self.assertEqual(ip.version, "1.0.0")

    def test_update_not_installed_raises(self):
        with self.assertRaises(KeyError):
            self.installer.update("missing")


# ------------------------------------------------------------------
# Verify integrity
# ------------------------------------------------------------------

class TestPluginInstaller2Verify(_InstallerTestBase):
    def test_verify_valid(self):
        self.installer.install(_make())
        self.assertTrue(self.installer.verify_integrity("my-plugin"))

    def test_verify_tampered(self):
        ip = self.installer.install(_make())
        self.written[ip.path] = "tampered content"
        self.assertFalse(self.installer.verify_integrity("my-plugin"))

    def test_verify_not_installed(self):
        self.assertFalse(self.installer.verify_integrity("nope"))

    def test_verify_read_error(self):
        installer = PluginInstaller2(
            write_fn=lambda p, c: None,
            read_fn=lambda p: (_ for _ in ()).throw(OSError("read fail")),
            delete_fn=lambda p: None,
        )
        # Manually populate
        m = _make()
        ip = installer.install(m)
        self.assertFalse(installer.verify_integrity("my-plugin"))


if __name__ == "__main__":
    unittest.main()
