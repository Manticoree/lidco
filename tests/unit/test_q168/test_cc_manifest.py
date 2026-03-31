"""Tests for cc_manifest (Task 952)."""
from __future__ import annotations

import unittest

from lidco.compat.cc_manifest import (
    CCPluginManifest,
    parse_cc_manifest,
    to_lidco_manifest,
    _map_permissions,
)
from lidco.marketplace.manifest import Capability, TrustLevel


class TestCCPluginManifest(unittest.TestCase):
    def test_default_fields(self):
        m = CCPluginManifest()
        self.assertEqual(m.name, "")
        self.assertEqual(m.version, "")
        self.assertEqual(m.permissions, [])
        self.assertEqual(m.tools, [])
        self.assertEqual(m.user_config, {})

    def test_fields_assigned(self):
        m = CCPluginManifest(
            name="test-plugin",
            version="1.0.0",
            description="A test",
            author="alice",
            permissions=["read", "write"],
            tools=[{"name": "t1"}],
            user_config={"k": "v"},
            homepage="https://example.com",
            repository="https://github.com/a/b",
        )
        self.assertEqual(m.name, "test-plugin")
        self.assertEqual(m.author, "alice")
        self.assertEqual(len(m.tools), 1)
        self.assertEqual(m.user_config, {"k": "v"})


class TestParseCCManifest(unittest.TestCase):
    def test_parse_full(self):
        data = {
            "name": "my-plugin",
            "version": "2.1.0",
            "description": "desc",
            "author": "bob",
            "permissions": ["read", "network"],
            "tools": [{"name": "tool1"}],
            "userConfig": {"theme": "dark"},
            "homepage": "https://h.com",
            "repository": "https://r.com",
        }
        m = parse_cc_manifest(data)
        self.assertEqual(m.name, "my-plugin")
        self.assertEqual(m.version, "2.1.0")
        self.assertEqual(m.permissions, ["read", "network"])
        self.assertEqual(m.user_config, {"theme": "dark"})
        self.assertEqual(m.homepage, "https://h.com")

    def test_parse_minimal(self):
        m = parse_cc_manifest({})
        self.assertEqual(m.name, "")
        self.assertEqual(m.permissions, [])

    def test_parse_user_config_key(self):
        m = parse_cc_manifest({"user_config": {"a": 1}})
        self.assertEqual(m.user_config, {"a": 1})

    def test_parse_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            parse_cc_manifest("not a dict")  # type: ignore[arg-type]

    def test_parse_coerces_types(self):
        m = parse_cc_manifest({"name": 123, "version": 456})
        self.assertEqual(m.name, "123")
        self.assertEqual(m.version, "456")


class TestMapPermissions(unittest.TestCase):
    def test_standard_mapping(self):
        caps = _map_permissions(["read", "write", "network"])
        self.assertIn(Capability.FILE_READ, caps)
        self.assertIn(Capability.FILE_WRITE, caps)
        self.assertIn(Capability.NETWORK, caps)

    def test_alias_mapping(self):
        caps = _map_permissions(["exec", "db", "http"])
        self.assertIn(Capability.EXECUTE, caps)
        self.assertIn(Capability.DATABASE, caps)
        self.assertIn(Capability.NETWORK, caps)

    def test_deduplication(self):
        caps = _map_permissions(["read", "file_read", "files:read"])
        self.assertEqual(len(caps), 1)
        self.assertEqual(caps[0], Capability.FILE_READ)

    def test_unknown_permission_skipped(self):
        caps = _map_permissions(["unknown_perm", "read"])
        self.assertEqual(len(caps), 1)

    def test_empty_list(self):
        self.assertEqual(_map_permissions([]), [])

    def test_case_insensitive(self):
        caps = _map_permissions(["READ", "Network"])
        self.assertEqual(len(caps), 2)


class TestToLidcoManifest(unittest.TestCase):
    def test_basic_conversion(self):
        cc = CCPluginManifest(
            name="test",
            version="1.0.0",
            description="A plugin",
            author="dev",
            permissions=["read", "execute"],
        )
        lm = to_lidco_manifest(cc)
        self.assertEqual(lm.name, "test")
        self.assertEqual(lm.version, "1.0.0")
        self.assertIn(Capability.FILE_READ, lm.capabilities)
        self.assertIn(Capability.EXECUTE, lm.capabilities)

    def test_trust_level_community(self):
        cc = CCPluginManifest(
            name="t", version="1.0.0", description="d", author="a",
            homepage="https://h.com", repository="https://r.com",
        )
        lm = to_lidco_manifest(cc)
        self.assertEqual(lm.trust_level, TrustLevel.COMMUNITY)

    def test_trust_level_unverified(self):
        cc = CCPluginManifest(name="t", version="1.0.0", description="d", author="a")
        lm = to_lidco_manifest(cc)
        self.assertEqual(lm.trust_level, TrustLevel.UNVERIFIED)

    def test_missing_version_defaults(self):
        cc = CCPluginManifest(name="t", description="d", author="a")
        lm = to_lidco_manifest(cc)
        self.assertEqual(lm.version, "0.0.0")

    def test_homepage_falls_back_to_repository(self):
        cc = CCPluginManifest(name="t", version="1.0.0", description="d", author="a",
                              repository="https://repo.com")
        lm = to_lidco_manifest(cc)
        self.assertEqual(lm.homepage, "https://repo.com")
