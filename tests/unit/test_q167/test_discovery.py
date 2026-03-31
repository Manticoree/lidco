"""Tests for PluginDiscovery (Task 948)."""
from __future__ import annotations

import unittest

from lidco.marketplace.manifest import Capability, PluginManifest, TrustLevel
from lidco.marketplace.discovery import PluginDiscovery, SearchResult


def _plugin(name="p1", category="tools", author="alice", trust=TrustLevel.COMMUNITY, desc="a plugin"):
    return PluginManifest(
        name=name, version="1.0.0", description=desc, author=author,
        trust_level=trust, category=category,
    )


class TestSearchResult(unittest.TestCase):
    def test_defaults(self):
        r = SearchResult()
        self.assertEqual(r.plugins, [])
        self.assertEqual(r.total, 0)
        self.assertEqual(r.query, "")


class TestPluginDiscoveryInit(unittest.TestCase):
    def test_empty_registry(self):
        d = PluginDiscovery()
        self.assertEqual(d.browse(), [])

    def test_initial_registry(self):
        p = _plugin()
        d = PluginDiscovery(registry=[p])
        self.assertEqual(len(d.browse()), 1)


class TestAddPlugin(unittest.TestCase):
    def test_add_increases_count(self):
        d = PluginDiscovery()
        d.add_plugin(_plugin("a"))
        d.add_plugin(_plugin("b"))
        self.assertEqual(len(d.browse(limit=50)), 2)


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.d = PluginDiscovery()
        self.d.add_plugin(_plugin("linter", category="tools", desc="Lint your code"))
        self.d.add_plugin(_plugin("formatter", category="tools", desc="Format source"))
        self.d.add_plugin(_plugin("security-scan", category="security", desc="Scan for vulns"))

    def test_search_by_name(self):
        r = self.d.search("linter")
        self.assertEqual(r.total, 1)
        self.assertEqual(r.plugins[0].name, "linter")

    def test_search_by_description(self):
        r = self.d.search("Lint")
        self.assertEqual(r.total, 1)

    def test_search_case_insensitive(self):
        r = self.d.search("LINT")
        self.assertEqual(r.total, 1)

    def test_search_no_results(self):
        r = self.d.search("nonexistent")
        self.assertEqual(r.total, 0)

    def test_search_with_category_filter(self):
        r = self.d.search("scan", category="security")
        self.assertEqual(r.total, 1)
        r2 = self.d.search("scan", category="tools")
        self.assertEqual(r2.total, 0)

    def test_search_with_trust_filter(self):
        self.d.add_plugin(_plugin("verified-tool", trust=TrustLevel.VERIFIED, desc="trusted tool"))
        r = self.d.search("tool", trust_level=TrustLevel.VERIFIED)
        self.assertEqual(r.total, 1)
        self.assertEqual(r.plugins[0].name, "verified-tool")

    def test_search_query_stored(self):
        r = self.d.search("lint")
        self.assertEqual(r.query, "lint")


class TestBrowse(unittest.TestCase):
    def test_browse_all(self):
        d = PluginDiscovery()
        for i in range(5):
            d.add_plugin(_plugin(f"p{i}"))
        self.assertEqual(len(d.browse()), 5)

    def test_browse_limit(self):
        d = PluginDiscovery()
        for i in range(10):
            d.add_plugin(_plugin(f"p{i}"))
        self.assertEqual(len(d.browse(limit=3)), 3)

    def test_browse_category(self):
        d = PluginDiscovery()
        d.add_plugin(_plugin("a", category="x"))
        d.add_plugin(_plugin("b", category="y"))
        self.assertEqual(len(d.browse(category="x")), 1)


class TestGetAndCategories(unittest.TestCase):
    def test_get_existing(self):
        d = PluginDiscovery()
        d.add_plugin(_plugin("foo"))
        self.assertEqual(d.get("foo").name, "foo")

    def test_get_missing(self):
        d = PluginDiscovery()
        self.assertIsNone(d.get("nope"))

    def test_categories(self):
        d = PluginDiscovery()
        d.add_plugin(_plugin("a", category="tools"))
        d.add_plugin(_plugin("b", category="security"))
        d.add_plugin(_plugin("c", category="tools"))
        cats = d.categories()
        self.assertEqual(sorted(cats), ["security", "tools"])

    def test_by_author(self):
        d = PluginDiscovery()
        d.add_plugin(_plugin("a", author="alice"))
        d.add_plugin(_plugin("b", author="bob"))
        d.add_plugin(_plugin("c", author="alice"))
        self.assertEqual(len(d.by_author("alice")), 2)
        self.assertEqual(len(d.by_author("charlie")), 0)


if __name__ == "__main__":
    unittest.main()
