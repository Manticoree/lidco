"""Tests for PluginDiscovery2 (Task 1033)."""
from __future__ import annotations

import json
import unittest

from lidco.marketplace.manifest2 import (
    AuthorInfo,
    MarketplaceIndex,
    PluginCategory,
    PluginManifest2,
)
from lidco.marketplace.discovery2 import (
    PluginDiscovery2,
    SourceInfo,
    SourceType,
)


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
# SourceType
# ------------------------------------------------------------------

class TestSourceType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(SourceType.GIT.value, "git")
        self.assertEqual(SourceType.NPM.value, "npm")
        self.assertEqual(SourceType.LOCAL.value, "local")


# ------------------------------------------------------------------
# SourceInfo
# ------------------------------------------------------------------

class TestSourceInfo(unittest.TestCase):
    def test_fields(self):
        s = SourceInfo(source_type=SourceType.GIT, url="https://github.com/x/y.git", ref="main")
        self.assertEqual(s.source_type, SourceType.GIT)
        self.assertEqual(s.ref, "main")

    def test_default_ref(self):
        s = SourceInfo(source_type=SourceType.LOCAL, url="/path")
        self.assertEqual(s.ref, "")

    def test_frozen(self):
        s = SourceInfo(source_type=SourceType.LOCAL, url="/p")
        with self.assertRaises(AttributeError):
            s.url = "/q"  # type: ignore[misc]


# ------------------------------------------------------------------
# resolve_source
# ------------------------------------------------------------------

class TestResolveSource(unittest.TestCase):
    def test_git_prefix(self):
        info = PluginDiscovery2.resolve_source("git+https://github.com/x/y")
        self.assertEqual(info.source_type, SourceType.GIT)
        self.assertEqual(info.url, "https://github.com/x/y")

    def test_git_prefix_with_ref(self):
        info = PluginDiscovery2.resolve_source("git+https://github.com/x/y@v1.0")
        self.assertEqual(info.source_type, SourceType.GIT)
        self.assertEqual(info.ref, "v1.0")

    def test_git_suffix(self):
        info = PluginDiscovery2.resolve_source("https://github.com/x/y.git")
        self.assertEqual(info.source_type, SourceType.GIT)

    def test_npm(self):
        info = PluginDiscovery2.resolve_source("npm:my-plugin")
        self.assertEqual(info.source_type, SourceType.NPM)
        self.assertEqual(info.url, "my-plugin")

    def test_local(self):
        info = PluginDiscovery2.resolve_source("/home/user/plugin")
        self.assertEqual(info.source_type, SourceType.LOCAL)
        self.assertEqual(info.url, "/home/user/plugin")

    def test_empty_string(self):
        info = PluginDiscovery2.resolve_source("")
        self.assertEqual(info.source_type, SourceType.LOCAL)
        self.assertEqual(info.url, "")

    def test_whitespace_stripped(self):
        info = PluginDiscovery2.resolve_source("  npm:foo  ")
        self.assertEqual(info.source_type, SourceType.NPM)
        self.assertEqual(info.url, "foo")


# ------------------------------------------------------------------
# PluginDiscovery2
# ------------------------------------------------------------------

class TestPluginDiscovery2(unittest.TestCase):
    def setUp(self):
        self.m1 = _make(name="alpha", description="Alpha tool", category=PluginCategory.DEVELOPMENT)
        self.m2 = _make(name="beta", description="Beta security", category=PluginCategory.SECURITY)
        self.m3 = _make(name="gamma", description="Gamma learning", category=PluginCategory.LEARNING)
        self.index = MarketplaceIndex([self.m1, self.m2, self.m3])
        self.discovery = PluginDiscovery2(index=self.index)

    def test_search_by_name(self):
        results = self.discovery.search("alpha")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "alpha")

    def test_search_by_description(self):
        results = self.discovery.search("security")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "beta")

    def test_search_with_category_filter(self):
        results = self.discovery.search("a", category=PluginCategory.DEVELOPMENT)
        names = [r.name for r in results]
        self.assertIn("alpha", names)
        self.assertNotIn("gamma", names)

    def test_search_no_match(self):
        results = self.discovery.search("zzzzz")
        self.assertEqual(len(results), 0)

    def test_list_available(self):
        plugins = self.discovery.list_available()
        self.assertEqual(len(plugins), 3)

    def test_list_by_category(self):
        plugins = self.discovery.list_by_category(PluginCategory.SECURITY)
        self.assertEqual(len(plugins), 1)

    def test_get_found(self):
        p = self.discovery.get("beta")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "beta")

    def test_get_not_found(self):
        p = self.discovery.get("nope")
        self.assertIsNone(p)

    def test_set_index_immutable(self):
        new_index = MarketplaceIndex()
        d2 = self.discovery.set_index(new_index)
        self.assertEqual(len(d2.list_available()), 0)
        self.assertEqual(len(self.discovery.list_available()), 3)

    def test_empty_discovery(self):
        d = PluginDiscovery2()
        self.assertEqual(len(d.list_available()), 0)


# ------------------------------------------------------------------
# fetch_manifest
# ------------------------------------------------------------------

class TestFetchManifest(unittest.TestCase):
    def test_fetch_local(self):
        manifest_data = {
            "name": "local-plug",
            "version": "1.0.0",
            "description": "desc",
            "author": {"name": "dev"},
            "category": "productivity",
        }
        source = SourceInfo(source_type=SourceType.LOCAL, url="/some/path")
        d = PluginDiscovery2()
        m = d.fetch_manifest(source, read_fn=lambda p: json.dumps(manifest_data))
        self.assertEqual(m.name, "local-plug")
        self.assertEqual(m.category, PluginCategory.PRODUCTIVITY)

    def test_fetch_git_not_implemented(self):
        source = SourceInfo(source_type=SourceType.GIT, url="https://x.git")
        d = PluginDiscovery2()
        with self.assertRaises(NotImplementedError):
            d.fetch_manifest(source)

    def test_fetch_npm_not_implemented(self):
        source = SourceInfo(source_type=SourceType.NPM, url="my-pkg")
        d = PluginDiscovery2()
        with self.assertRaises(NotImplementedError):
            d.fetch_manifest(source)


if __name__ == "__main__":
    unittest.main()
