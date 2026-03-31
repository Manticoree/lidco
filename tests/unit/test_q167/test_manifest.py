"""Tests for PluginManifest (Task 947)."""
from __future__ import annotations

import unittest

from lidco.marketplace.manifest import Capability, PluginManifest, TrustLevel


def _make(**overrides) -> PluginManifest:
    defaults = dict(
        name="test-plugin",
        version="1.0.0",
        description="A test plugin",
        author="tester",
        trust_level=TrustLevel.COMMUNITY,
    )
    defaults.update(overrides)
    return PluginManifest(**defaults)


class TestTrustLevel(unittest.TestCase):
    def test_values(self):
        self.assertEqual(TrustLevel.VERIFIED.value, "verified")
        self.assertEqual(TrustLevel.COMMUNITY.value, "community")
        self.assertEqual(TrustLevel.UNVERIFIED.value, "unverified")


class TestCapability(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Capability.FILE_READ.value, "file_read")
        self.assertEqual(Capability.FILE_WRITE.value, "file_write")
        self.assertEqual(Capability.NETWORK.value, "network")
        self.assertEqual(Capability.EXECUTE.value, "execute")
        self.assertEqual(Capability.GIT.value, "git")
        self.assertEqual(Capability.DATABASE.value, "database")


class TestPluginManifestFields(unittest.TestCase):
    def test_basic_fields(self):
        m = _make()
        self.assertEqual(m.name, "test-plugin")
        self.assertEqual(m.version, "1.0.0")
        self.assertEqual(m.trust_level, TrustLevel.COMMUNITY)

    def test_default_lists(self):
        m = _make()
        self.assertEqual(m.capabilities, [])
        self.assertEqual(m.dependencies, [])

    def test_default_strings(self):
        m = _make()
        self.assertEqual(m.homepage, "")
        self.assertEqual(m.checksum, "")
        self.assertEqual(m.category, "")
        self.assertEqual(m.min_lidco_version, "")

    def test_capabilities_list(self):
        m = _make(capabilities=[Capability.NETWORK, Capability.GIT])
        self.assertEqual(len(m.capabilities), 2)


class TestPluginManifestSerialization(unittest.TestCase):
    def test_to_dict_basic(self):
        m = _make(capabilities=[Capability.FILE_READ])
        d = m.to_dict()
        self.assertEqual(d["name"], "test-plugin")
        self.assertEqual(d["trust_level"], "community")
        self.assertEqual(d["capabilities"], ["file_read"])

    def test_from_dict_basic(self):
        d = {
            "name": "foo",
            "version": "2.0.0",
            "description": "desc",
            "author": "bar",
            "trust_level": "verified",
            "capabilities": ["network"],
        }
        m = PluginManifest.from_dict(d)
        self.assertEqual(m.name, "foo")
        self.assertEqual(m.trust_level, TrustLevel.VERIFIED)
        self.assertEqual(m.capabilities, [Capability.NETWORK])

    def test_roundtrip(self):
        m = _make(capabilities=[Capability.EXECUTE], homepage="https://x.com")
        d = m.to_dict()
        m2 = PluginManifest.from_dict(d)
        self.assertEqual(m2.name, m.name)
        self.assertEqual(m2.trust_level, m.trust_level)
        self.assertEqual(m2.capabilities, m.capabilities)
        self.assertEqual(m2.homepage, m.homepage)

    def test_from_dict_defaults(self):
        d = {"name": "a", "version": "1.0.0", "description": "d", "author": "x", "trust_level": "unverified"}
        m = PluginManifest.from_dict(d)
        self.assertEqual(m.capabilities, [])
        self.assertEqual(m.dependencies, [])
        self.assertEqual(m.homepage, "")


class TestPluginManifestValidation(unittest.TestCase):
    def test_valid_manifest(self):
        m = _make()
        self.assertEqual(m.validate(), [])

    def test_missing_name(self):
        m = _make(name="")
        errors = m.validate()
        self.assertIn("name is required", errors)

    def test_missing_version(self):
        m = _make(version="")
        errors = m.validate()
        self.assertIn("version is required", errors)

    def test_bad_version_format(self):
        m = _make(version="abc")
        errors = m.validate()
        self.assertTrue(any("semver" in e for e in errors))

    def test_missing_description(self):
        m = _make(description="")
        errors = m.validate()
        self.assertIn("description is required", errors)

    def test_missing_author(self):
        m = _make(author="")
        errors = m.validate()
        self.assertIn("author is required", errors)

    def test_multiple_errors(self):
        m = PluginManifest(name="", version="", description="", author="", trust_level=TrustLevel.UNVERIFIED)
        errors = m.validate()
        self.assertGreaterEqual(len(errors), 3)


if __name__ == "__main__":
    unittest.main()
