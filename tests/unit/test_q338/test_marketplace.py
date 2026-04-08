"""Tests for PluginMarketplaceV2 (Task 1802)."""
from __future__ import annotations

import unittest

from lidco.community.marketplace import (
    CompatEntry,
    MarketplacePlugin,
    PluginMarketplaceV2,
    PluginReview,
    PluginStatus,
)


def _plugin(name: str = "test-plugin", **kw) -> MarketplacePlugin:
    defaults = dict(
        version="1.0.0", description="A test plugin", author="alice", category="tools",
    )
    defaults.update(kw)
    return MarketplacePlugin(name=name, **defaults)


class TestPluginReview(unittest.TestCase):
    def test_valid_review(self):
        r = PluginReview(author="bob", rating=4, comment="great")
        self.assertEqual(r.rating, 4)
        self.assertGreater(r.created_at, 0)

    def test_invalid_rating_low(self):
        with self.assertRaises(ValueError):
            PluginReview(author="bob", rating=0)

    def test_invalid_rating_high(self):
        with self.assertRaises(ValueError):
            PluginReview(author="bob", rating=6)


class TestMarketplacePlugin(unittest.TestCase):
    def test_defaults(self):
        p = _plugin()
        self.assertEqual(p.name, "test-plugin")
        self.assertEqual(p.status, PluginStatus.PUBLISHED)
        self.assertEqual(p.downloads, 0)
        self.assertEqual(p.average_rating, 0.0)
        self.assertEqual(p.review_count, 0)

    def test_average_rating(self):
        p = _plugin()
        p = p.add_review(PluginReview(author="a", rating=4))
        p = p.add_review(PluginReview(author="b", rating=2))
        self.assertAlmostEqual(p.average_rating, 3.0)

    def test_increment_downloads(self):
        p = _plugin()
        p2 = p.increment_downloads()
        self.assertEqual(p.downloads, 0)  # immutable
        self.assertEqual(p2.downloads, 1)

    def test_add_compat_entry(self):
        p = _plugin()
        entry = CompatEntry(plugin_version="1.0.0", lidco_version="2.0.0", compatible=True)
        p2 = p.add_compat_entry(entry)
        self.assertEqual(len(p.compat_matrix), 0)
        self.assertEqual(len(p2.compat_matrix), 1)

    def test_to_dict(self):
        p = _plugin(tags=["lint"])
        d = p.to_dict()
        self.assertEqual(d["name"], "test-plugin")
        self.assertEqual(d["tags"], ["lint"])
        self.assertIn("average_rating", d)


class TestPluginMarketplaceV2(unittest.TestCase):
    def setUp(self):
        self.mp = PluginMarketplaceV2()

    def test_empty(self):
        self.assertEqual(self.mp.count, 0)

    def test_publish_and_get(self):
        p = _plugin("linter")
        self.mp.publish(p)
        self.assertEqual(self.mp.count, 1)
        got = self.mp.get("linter")
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "linter")

    def test_publish_requires_name(self):
        with self.assertRaises(ValueError):
            self.mp.publish(MarketplacePlugin(name="", version="1.0.0", description="", author="a"))

    def test_remove(self):
        self.mp.publish(_plugin("x"))
        self.assertTrue(self.mp.remove("x"))
        self.assertFalse(self.mp.remove("x"))
        self.assertEqual(self.mp.count, 0)

    def test_search(self):
        self.mp.publish(_plugin("linter", description="Lint code"))
        self.mp.publish(_plugin("formatter", description="Format code"))
        results = self.mp.search("lint")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "linter")

    def test_search_by_tag(self):
        self.mp.publish(_plugin("x", tags=["security"]))
        results = self.mp.search("security")
        self.assertEqual(len(results), 1)

    def test_search_filters_by_category(self):
        self.mp.publish(_plugin("a", category="tools", description="match"))
        self.mp.publish(_plugin("b", category="security", description="match"))
        results = self.mp.search("match", category="tools")
        self.assertEqual(len(results), 1)

    def test_browse(self):
        self.mp.publish(_plugin("a"))
        self.mp.publish(_plugin("b"))
        all_plugins = self.mp.browse()
        self.assertEqual(len(all_plugins), 2)

    def test_browse_by_category(self):
        self.mp.publish(_plugin("a", category="tools"))
        self.mp.publish(_plugin("b", category="security"))
        result = self.mp.browse(category="tools")
        self.assertEqual(len(result), 1)

    def test_browse_excludes_non_published(self):
        self.mp.publish(_plugin("a", status=PluginStatus.DEPRECATED))
        self.assertEqual(len(self.mp.browse()), 0)

    def test_top_rated(self):
        self.mp.publish(_plugin("a"))
        self.mp.add_review("a", PluginReview(author="u", rating=5))
        self.mp.publish(_plugin("b"))
        self.mp.add_review("b", PluginReview(author="u", rating=3))
        top = self.mp.top_rated()
        self.assertEqual(top[0].name, "a")

    def test_add_review_not_found(self):
        self.assertFalse(self.mp.add_review("nope", PluginReview(author="u", rating=3)))

    def test_record_download(self):
        self.mp.publish(_plugin("x"))
        self.assertTrue(self.mp.record_download("x"))
        self.assertEqual(self.mp.get("x").downloads, 1)

    def test_record_download_not_found(self):
        self.assertFalse(self.mp.record_download("nope"))

    def test_check_update_newer(self):
        self.mp.publish(_plugin("x", version="2.0.0"))
        result = self.mp.check_update("x", "1.0.0")
        self.assertEqual(result, "2.0.0")

    def test_check_update_up_to_date(self):
        self.mp.publish(_plugin("x", version="1.0.0"))
        self.assertIsNone(self.mp.check_update("x", "1.0.0"))

    def test_check_update_not_found(self):
        self.assertIsNone(self.mp.check_update("nope", "1.0.0"))

    def test_compat_matrix(self):
        self.mp.publish(_plugin("x"))
        entry = CompatEntry(plugin_version="1.0.0", lidco_version="2.0.0", compatible=True)
        self.assertTrue(self.mp.add_compat_entry("x", entry))
        matrix = self.mp.compat_matrix("x")
        self.assertEqual(len(matrix), 1)
        self.assertTrue(matrix[0].compatible)

    def test_compat_matrix_not_found(self):
        self.assertEqual(self.mp.compat_matrix("nope"), [])
        self.assertFalse(self.mp.add_compat_entry("nope", CompatEntry("1", "2", True)))

    def test_stats(self):
        self.mp.publish(_plugin("a", category="tools"))
        self.mp.publish(_plugin("b", category="security"))
        st = self.mp.stats()
        self.assertEqual(st["total_plugins"], 2)
        self.assertIn("tools", st["categories"])
        self.assertIn("security", st["categories"])


if __name__ == "__main__":
    unittest.main()
