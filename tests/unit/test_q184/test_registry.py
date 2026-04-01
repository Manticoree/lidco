"""Tests for MarketplaceRegistry (Task 1035)."""
from __future__ import annotations

import json
import unittest

from lidco.marketplace.manifest2 import (
    AuthorInfo,
    PluginCategory,
    PluginManifest2,
)
from lidco.marketplace.registry2 import MarketplaceRegistry


def _make(name="test-plugin", **overrides) -> PluginManifest2:
    defaults = dict(
        name=name,
        version="1.0.0",
        description="A test plugin",
        author=AuthorInfo(name="tester"),
        category=PluginCategory.DEVELOPMENT,
    )
    defaults.update(overrides)
    return PluginManifest2(**defaults)


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

class TestMarketplaceRegistryRegister(unittest.TestCase):
    def test_register(self):
        reg = MarketplaceRegistry()
        reg.register(_make())
        self.assertEqual(len(reg), 1)

    def test_register_replaces_same_name(self):
        reg = MarketplaceRegistry()
        reg.register(_make(name="a", version="1.0.0"))
        reg.register(_make(name="a", version="2.0.0"))
        self.assertEqual(len(reg), 1)
        self.assertEqual(reg.get("a").version, "2.0.0")

    def test_register_multiple(self):
        reg = MarketplaceRegistry()
        reg.register(_make(name="a"))
        reg.register(_make(name="b"))
        self.assertEqual(len(reg), 2)

    def test_unregister_existing(self):
        reg = MarketplaceRegistry()
        reg.register(_make())
        self.assertTrue(reg.unregister("test-plugin"))
        self.assertEqual(len(reg), 0)

    def test_unregister_nonexistent(self):
        reg = MarketplaceRegistry()
        self.assertFalse(reg.unregister("nope"))


# ------------------------------------------------------------------
# Lookup
# ------------------------------------------------------------------

class TestMarketplaceRegistryLookup(unittest.TestCase):
    def setUp(self):
        self.reg = MarketplaceRegistry()
        self.reg.register(_make(name="alpha", description="Alpha tool"))
        self.reg.register(_make(name="beta", description="Beta tool", category=PluginCategory.SECURITY))

    def test_get_found(self):
        p = self.reg.get("alpha")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "alpha")

    def test_get_not_found(self):
        self.assertIsNone(self.reg.get("nope"))

    def test_search(self):
        results = self.reg.search("alpha")
        self.assertEqual(len(results), 1)

    def test_search_by_description(self):
        results = self.reg.search("tool")
        self.assertEqual(len(results), 2)

    def test_search_no_match(self):
        results = self.reg.search("zzz")
        self.assertEqual(len(results), 0)

    def test_list_all(self):
        self.assertEqual(len(self.reg.list_all()), 2)

    def test_contains(self):
        self.assertIn("alpha", self.reg)
        self.assertNotIn("nope", self.reg)


# ------------------------------------------------------------------
# Categories
# ------------------------------------------------------------------

class TestMarketplaceRegistryCategories(unittest.TestCase):
    def test_categories(self):
        reg = MarketplaceRegistry()
        reg.register(_make(name="a", category=PluginCategory.DEVELOPMENT))
        reg.register(_make(name="b", category=PluginCategory.DEVELOPMENT))
        reg.register(_make(name="c", category=PluginCategory.SECURITY))
        cats = reg.categories()
        self.assertIn("development", cats)
        self.assertIn("security", cats)
        self.assertEqual(len(cats["development"]), 2)
        self.assertEqual(len(cats["security"]), 1)

    def test_categories_empty(self):
        reg = MarketplaceRegistry()
        self.assertEqual(reg.categories(), {})


# ------------------------------------------------------------------
# Import / Export
# ------------------------------------------------------------------

class TestMarketplaceRegistryImportExport(unittest.TestCase):
    def test_export_index(self):
        written: dict[str, str] = {}
        reg = MarketplaceRegistry()
        reg.register(_make(name="a"))
        reg.register(_make(name="b"))
        reg.export_index("/out.json", write_fn=lambda p, c: written.update({p: c}))
        self.assertIn("/out.json", written)
        data = json.loads(written["/out.json"])
        self.assertEqual(data["version"], "1.0")
        self.assertEqual(len(data["plugins"]), 2)

    def test_import_index(self):
        data = {
            "version": "1.0",
            "plugins": [
                {"name": "x", "version": "1.0.0", "description": "d", "author": {"name": "a"}, "category": "development"},
                {"name": "y", "version": "2.0.0", "description": "e", "author": {"name": "b"}, "category": "security"},
            ],
        }
        reg = MarketplaceRegistry()
        count = reg.import_index("/in.json", read_fn=lambda p: json.dumps(data))
        self.assertEqual(count, 2)
        self.assertEqual(len(reg), 2)
        self.assertIsNotNone(reg.get("x"))
        self.assertIsNotNone(reg.get("y"))

    def test_import_empty_index(self):
        data = {"version": "1.0", "plugins": []}
        reg = MarketplaceRegistry()
        count = reg.import_index("/in.json", read_fn=lambda p: json.dumps(data))
        self.assertEqual(count, 0)

    def test_roundtrip_export_import(self):
        written: dict[str, str] = {}
        reg1 = MarketplaceRegistry()
        reg1.register(_make(name="a", description="Alpha"))
        reg1.export_index("/f.json", write_fn=lambda p, c: written.update({p: c}))

        reg2 = MarketplaceRegistry()
        reg2.import_index("/f.json", read_fn=lambda p: written[p])
        self.assertEqual(len(reg2), 1)
        self.assertEqual(reg2.get("a").description, "Alpha")


if __name__ == "__main__":
    unittest.main()
