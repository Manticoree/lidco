"""Tests for Q144 ConfigVersion."""
from __future__ import annotations

import unittest

from lidco.config.config_version import ConfigVersion, VersionedConfig


class TestVersionedConfig(unittest.TestCase):
    def test_dataclass_fields(self):
        vc = VersionedConfig(version="1.0.0", data={"a": 1}, created_at=100.0)
        self.assertEqual(vc.version, "1.0.0")
        self.assertEqual(vc.data, {"a": 1})
        self.assertEqual(vc.created_at, 100.0)
        self.assertIsNone(vc.migrated_from)

    def test_migrated_from(self):
        vc = VersionedConfig(version="2.0.0", data={}, migrated_from="1.0.0")
        self.assertEqual(vc.migrated_from, "1.0.0")


class TestConfigVersion(unittest.TestCase):
    def setUp(self):
        self.cv = ConfigVersion()

    # --- stamp ---

    def test_stamp_returns_versioned_config(self):
        vc = self.cv.stamp({"key": "val"}, "1.0.0")
        self.assertIsInstance(vc, VersionedConfig)
        self.assertEqual(vc.version, "1.0.0")

    def test_stamp_includes_version_key(self):
        vc = self.cv.stamp({"x": 1}, "2.0.0")
        self.assertEqual(vc.data[ConfigVersion.VERSION_KEY], "2.0.0")

    def test_stamp_includes_created_at(self):
        vc = self.cv.stamp({}, "1.0.0")
        self.assertIn(ConfigVersion.CREATED_KEY, vc.data)
        self.assertGreater(vc.created_at, 0)

    def test_stamp_preserves_original_data(self):
        vc = self.cv.stamp({"a": 1, "b": 2}, "1.0.0")
        self.assertEqual(vc.data["a"], 1)
        self.assertEqual(vc.data["b"], 2)

    # --- get_version ---

    def test_get_version_present(self):
        data = {ConfigVersion.VERSION_KEY: "3.1.0"}
        self.assertEqual(self.cv.get_version(data), "3.1.0")

    def test_get_version_absent(self):
        self.assertIsNone(self.cv.get_version({"foo": "bar"}))

    # --- is_current ---

    def test_is_current_true(self):
        data = {ConfigVersion.VERSION_KEY: "1.0.0"}
        self.assertTrue(self.cv.is_current(data, "1.0.0"))

    def test_is_current_false(self):
        data = {ConfigVersion.VERSION_KEY: "1.0.0"}
        self.assertFalse(self.cv.is_current(data, "2.0.0"))

    def test_is_current_missing_version(self):
        self.assertFalse(self.cv.is_current({}, "1.0.0"))

    # --- needs_migration ---

    def test_needs_migration_true_different(self):
        data = {ConfigVersion.VERSION_KEY: "1.0.0"}
        self.assertTrue(self.cv.needs_migration(data, "2.0.0"))

    def test_needs_migration_false_same(self):
        data = {ConfigVersion.VERSION_KEY: "1.0.0"}
        self.assertFalse(self.cv.needs_migration(data, "1.0.0"))

    def test_needs_migration_true_no_version(self):
        self.assertTrue(self.cv.needs_migration({}, "1.0.0"))

    # --- compare_versions ---

    def test_compare_equal(self):
        self.assertEqual(self.cv.compare_versions("1.0.0", "1.0.0"), 0)

    def test_compare_less(self):
        self.assertEqual(self.cv.compare_versions("1.0.0", "2.0.0"), -1)

    def test_compare_greater(self):
        self.assertEqual(self.cv.compare_versions("2.0.0", "1.0.0"), 1)

    def test_compare_minor(self):
        self.assertEqual(self.cv.compare_versions("1.1.0", "1.2.0"), -1)

    def test_compare_patch(self):
        self.assertEqual(self.cv.compare_versions("1.0.1", "1.0.0"), 1)

    # --- parse_version ---

    def test_parse_version_simple(self):
        self.assertEqual(ConfigVersion.parse_version("1.2.3"), (1, 2, 3))

    def test_parse_version_zeros(self):
        self.assertEqual(ConfigVersion.parse_version("0.0.0"), (0, 0, 0))

    def test_parse_version_invalid_two_parts(self):
        with self.assertRaises(ValueError):
            ConfigVersion.parse_version("1.0")

    def test_parse_version_invalid_non_numeric(self):
        with self.assertRaises(ValueError):
            ConfigVersion.parse_version("a.b.c")


if __name__ == "__main__":
    unittest.main()
