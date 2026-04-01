"""Tests for PluginManifest2 and related (Task 1032)."""
from __future__ import annotations

import json
import unittest

from lidco.marketplace.manifest2 import (
    AuthorInfo,
    MarketplaceIndex,
    PluginCategory,
    PluginManifest2,
    PluginManifestSchema,
    load_manifest,
    save_manifest,
)


def _make(**overrides) -> PluginManifest2:
    defaults = dict(
        name="test-plugin",
        version="1.0.0",
        description="A test plugin",
        author=AuthorInfo(name="tester", email="t@example.com"),
        category=PluginCategory.DEVELOPMENT,
    )
    defaults.update(overrides)
    return PluginManifest2(**defaults)


# ------------------------------------------------------------------
# AuthorInfo
# ------------------------------------------------------------------

class TestAuthorInfo(unittest.TestCase):
    def test_fields(self):
        a = AuthorInfo(name="Alice", email="alice@x.com")
        self.assertEqual(a.name, "Alice")
        self.assertEqual(a.email, "alice@x.com")

    def test_default_email(self):
        a = AuthorInfo(name="Bob")
        self.assertEqual(a.email, "")

    def test_frozen(self):
        a = AuthorInfo(name="C")
        with self.assertRaises(AttributeError):
            a.name = "D"  # type: ignore[misc]


# ------------------------------------------------------------------
# PluginCategory
# ------------------------------------------------------------------

class TestPluginCategory(unittest.TestCase):
    def test_values(self):
        self.assertEqual(PluginCategory.DEVELOPMENT.value, "development")
        self.assertEqual(PluginCategory.PRODUCTIVITY.value, "productivity")
        self.assertEqual(PluginCategory.LEARNING.value, "learning")
        self.assertEqual(PluginCategory.SECURITY.value, "security")

    def test_all_members(self):
        self.assertEqual(len(PluginCategory), 4)


# ------------------------------------------------------------------
# PluginManifest2
# ------------------------------------------------------------------

class TestPluginManifest2(unittest.TestCase):
    def test_basic_fields(self):
        m = _make()
        self.assertEqual(m.name, "test-plugin")
        self.assertEqual(m.version, "1.0.0")
        self.assertEqual(m.category, PluginCategory.DEVELOPMENT)
        self.assertEqual(m.author.name, "tester")

    def test_defaults(self):
        m = _make()
        self.assertEqual(m.source, "")
        self.assertEqual(m.dependencies, ())
        self.assertEqual(m.tags, ())
        self.assertEqual(m.homepage, "")
        self.assertEqual(m.license, "")

    def test_frozen(self):
        m = _make()
        with self.assertRaises(AttributeError):
            m.name = "changed"  # type: ignore[misc]

    def test_to_dict(self):
        m = _make(tags=("cli", "dev"), source="npm:my-plugin")
        d = m.to_dict()
        self.assertEqual(d["name"], "test-plugin")
        self.assertEqual(d["category"], "development")
        self.assertEqual(d["author"]["name"], "tester")
        self.assertEqual(d["tags"], ["cli", "dev"])
        self.assertEqual(d["source"], "npm:my-plugin")

    def test_from_dict(self):
        d = {
            "name": "foo",
            "version": "2.0.0",
            "description": "desc",
            "author": {"name": "bar", "email": "b@x.com"},
            "category": "security",
        }
        m = PluginManifest2.from_dict(d)
        self.assertEqual(m.name, "foo")
        self.assertEqual(m.category, PluginCategory.SECURITY)
        self.assertEqual(m.author.email, "b@x.com")

    def test_from_dict_author_string(self):
        d = {
            "name": "a",
            "version": "1.0.0",
            "description": "d",
            "author": "simple-author",
            "category": "learning",
        }
        m = PluginManifest2.from_dict(d)
        self.assertEqual(m.author.name, "simple-author")

    def test_roundtrip(self):
        m = _make(homepage="https://example.com", license="MIT")
        d = m.to_dict()
        m2 = PluginManifest2.from_dict(d)
        self.assertEqual(m.name, m2.name)
        self.assertEqual(m.version, m2.version)
        self.assertEqual(m.author.name, m2.author.name)
        self.assertEqual(m.category, m2.category)
        self.assertEqual(m.homepage, m2.homepage)


# ------------------------------------------------------------------
# PluginManifestSchema
# ------------------------------------------------------------------

class TestPluginManifestSchema(unittest.TestCase):
    def test_valid(self):
        d = {
            "name": "x",
            "version": "1.0.0",
            "description": "d",
            "author": {"name": "a"},
            "category": "development",
        }
        self.assertEqual(PluginManifestSchema.validate(d), [])

    def test_missing_name(self):
        d = {"version": "1.0.0", "description": "d", "author": {"name": "a"}, "category": "development"}
        errors = PluginManifestSchema.validate(d)
        self.assertTrue(any("name" in e for e in errors))

    def test_missing_version(self):
        d = {"name": "x", "description": "d", "author": {"name": "a"}, "category": "development"}
        errors = PluginManifestSchema.validate(d)
        self.assertTrue(any("version" in e for e in errors))

    def test_bad_version(self):
        d = {"name": "x", "version": "abc", "description": "d", "author": {"name": "a"}, "category": "development"}
        errors = PluginManifestSchema.validate(d)
        self.assertTrue(any("semver" in e for e in errors))

    def test_invalid_category(self):
        d = {"name": "x", "version": "1.0.0", "description": "d", "author": {"name": "a"}, "category": "nope"}
        errors = PluginManifestSchema.validate(d)
        self.assertTrue(any("category" in e for e in errors))

    def test_missing_author_name(self):
        d = {"name": "x", "version": "1.0.0", "description": "d", "author": {"email": "a@b"}, "category": "development"}
        errors = PluginManifestSchema.validate(d)
        self.assertTrue(any("author.name" in e for e in errors))

    def test_multiple_errors(self):
        errors = PluginManifestSchema.validate({})
        self.assertGreaterEqual(len(errors), 3)


# ------------------------------------------------------------------
# load_manifest / save_manifest
# ------------------------------------------------------------------

class TestLoadSaveManifest(unittest.TestCase):
    def test_load_manifest(self):
        data = {
            "name": "x",
            "version": "1.0.0",
            "description": "d",
            "author": {"name": "a"},
            "category": "development",
        }
        m = load_manifest("/fake.json", read_fn=lambda p: json.dumps(data))
        self.assertEqual(m.name, "x")

    def test_load_manifest_invalid_raises(self):
        data = {"name": ""}
        with self.assertRaises(ValueError):
            load_manifest("/fake.json", read_fn=lambda p: json.dumps(data))

    def test_save_manifest(self):
        written: dict[str, str] = {}
        m = _make()
        save_manifest(m, "/out.json", write_fn=lambda p, c: written.update({p: c}))
        self.assertIn("/out.json", written)
        parsed = json.loads(written["/out.json"])
        self.assertEqual(parsed["name"], "test-plugin")


# ------------------------------------------------------------------
# MarketplaceIndex
# ------------------------------------------------------------------

class TestMarketplaceIndex(unittest.TestCase):
    def test_empty(self):
        idx = MarketplaceIndex()
        self.assertEqual(len(idx), 0)

    def test_add_immutable(self):
        idx = MarketplaceIndex()
        m = _make()
        idx2 = idx.add(m)
        self.assertEqual(len(idx), 0)
        self.assertEqual(len(idx2), 1)

    def test_remove_immutable(self):
        m = _make()
        idx = MarketplaceIndex([m])
        idx2 = idx.remove("test-plugin")
        self.assertEqual(len(idx), 1)
        self.assertEqual(len(idx2), 0)

    def test_search(self):
        m1 = _make(name="alpha-tool", description="Alpha tool")
        m2 = _make(name="beta", description="Beta tool")
        idx = MarketplaceIndex([m1, m2])
        self.assertEqual(len(idx.search("alpha")), 1)
        self.assertEqual(len(idx.search("tool")), 2)

    def test_filter_by_category(self):
        m1 = _make(name="a", category=PluginCategory.SECURITY)
        m2 = _make(name="b", category=PluginCategory.DEVELOPMENT)
        idx = MarketplaceIndex([m1, m2])
        self.assertEqual(len(idx.filter_by_category(PluginCategory.SECURITY)), 1)

    def test_filter_by_author(self):
        m1 = _make(name="a", author=AuthorInfo(name="Alice"))
        m2 = _make(name="b", author=AuthorInfo(name="Bob"))
        idx = MarketplaceIndex([m1, m2])
        self.assertEqual(len(idx.filter_by_author("Alice")), 1)

    def test_get(self):
        m = _make()
        idx = MarketplaceIndex([m])
        self.assertEqual(idx.get("test-plugin"), m)
        self.assertIsNone(idx.get("nope"))

    def test_contains(self):
        m = _make()
        idx = MarketplaceIndex([m])
        self.assertIn("test-plugin", idx)
        self.assertNotIn("nope", idx)

    def test_categories(self):
        m1 = _make(name="a", category=PluginCategory.SECURITY)
        m2 = _make(name="b", category=PluginCategory.SECURITY)
        m3 = _make(name="c", category=PluginCategory.LEARNING)
        idx = MarketplaceIndex([m1, m2, m3])
        cats = idx.categories()
        self.assertEqual(cats["security"], 2)
        self.assertEqual(cats["learning"], 1)


if __name__ == "__main__":
    unittest.main()
