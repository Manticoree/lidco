"""Tests for PluginApiCompatibility (Q345)."""
from __future__ import annotations

import unittest


def _compat():
    from lidco.stability.plugin_compat import PluginApiCompatibility
    return PluginApiCompatibility()


def _api(version, *methods):
    return {"version": version, "methods": list(methods)}


class TestCheckCompatibility(unittest.TestCase):
    def test_identical_apis_are_compatible(self):
        api = _api("1.0.0", "init", "run", "shutdown")
        result = _compat().check_compatibility(api, api)
        self.assertTrue(result["compatible"])
        self.assertEqual(result["missing_methods"], [])
        self.assertEqual(result["extra_methods"], [])
        self.assertTrue(result["version_ok"])

    def test_missing_host_method_makes_incompatible(self):
        plugin = _api("1.0.0", "init", "run")
        host = _api("1.0.0", "init", "run", "health")
        result = _compat().check_compatibility(plugin, host)
        self.assertFalse(result["compatible"])
        self.assertIn("health", result["missing_methods"])

    def test_extra_plugin_methods_not_incompatible(self):
        plugin = _api("1.0.0", "init", "run", "extra")
        host = _api("1.0.0", "init", "run")
        result = _compat().check_compatibility(plugin, host)
        self.assertTrue(result["compatible"])
        self.assertIn("extra", result["extra_methods"])

    def test_different_major_version_not_ok(self):
        plugin = _api("2.0.0", "init")
        host = _api("1.0.0", "init")
        result = _compat().check_compatibility(plugin, host)
        self.assertFalse(result["version_ok"])
        self.assertFalse(result["compatible"])

    def test_same_major_different_minor_is_version_ok(self):
        plugin = _api("1.3.0", "init")
        host = _api("1.0.0", "init")
        result = _compat().check_compatibility(plugin, host)
        self.assertTrue(result["version_ok"])


class TestTrackInterfaceVersions(unittest.TestCase):
    def test_single_interface_tracked(self):
        compat = _compat()
        ifaces = [{"name": "Logger", "version": "1.0.0", "methods": ["log", "debug"]}]
        result = compat.track_interface_versions(ifaces)
        self.assertIn("Logger", result)
        self.assertEqual(result["Logger"]["current_version"], "1.0.0")
        self.assertEqual(result["Logger"]["method_count"], 2)
        self.assertEqual(result["Logger"]["history_length"], 1)

    def test_multiple_calls_accumulate_history(self):
        compat = _compat()
        compat.track_interface_versions(
            [{"name": "Storage", "version": "1.0.0", "methods": ["get", "set"]}]
        )
        result = compat.track_interface_versions(
            [{"name": "Storage", "version": "1.1.0", "methods": ["get", "set", "delete"]}]
        )
        self.assertEqual(result["Storage"]["current_version"], "1.1.0")
        self.assertEqual(result["Storage"]["history_length"], 2)

    def test_tracks_multiple_interfaces(self):
        compat = _compat()
        ifaces = [
            {"name": "Auth", "version": "1.0.0", "methods": ["login", "logout"]},
            {"name": "Cache", "version": "2.1.0", "methods": ["get", "set", "clear"]},
        ]
        result = compat.track_interface_versions(ifaces)
        self.assertIn("Auth", result)
        self.assertIn("Cache", result)


class TestCheckMigrationNeeded(unittest.TestCase):
    def test_same_version_no_migration(self):
        result = _compat().check_migration_needed("1.0.0", "1.0.0")
        self.assertFalse(result["needs_migration"])
        self.assertFalse(result["breaking"])

    def test_major_bump_needs_migration_and_is_breaking(self):
        result = _compat().check_migration_needed("1.5.0", "2.0.0")
        self.assertTrue(result["needs_migration"])
        self.assertTrue(result["breaking"])

    def test_minor_bump_needs_migration_not_breaking(self):
        result = _compat().check_migration_needed("1.0.0", "1.1.0")
        self.assertTrue(result["needs_migration"])
        self.assertFalse(result["breaking"])

    def test_result_contains_versions(self):
        result = _compat().check_migration_needed("1.0.0", "2.0.0")
        self.assertEqual(result["from_version"], "1.0.0")
        self.assertEqual(result["to_version"], "2.0.0")


class TestGenerateMigrationGuide(unittest.TestCase):
    def test_guide_contains_version_header(self):
        old = _api("1.0.0", "init", "run")
        new = _api("2.0.0", "init", "run")
        guide = _compat().generate_migration_guide(old, new)
        self.assertIn("1.0.0", guide)
        self.assertIn("2.0.0", guide)

    def test_guide_lists_removed_methods(self):
        old = _api("1.0.0", "init", "run", "old_method")
        new = _api("2.0.0", "init", "run")
        guide = _compat().generate_migration_guide(old, new)
        self.assertIn("old_method", guide)
        self.assertIn("Removed", guide)

    def test_guide_lists_added_methods(self):
        old = _api("1.0.0", "init")
        new = _api("2.0.0", "init", "new_feature")
        guide = _compat().generate_migration_guide(old, new)
        self.assertIn("new_feature", guide)
        self.assertIn("New", guide)

    def test_guide_unchanged_methods_listed(self):
        old = _api("1.0.0", "init", "run")
        new = _api("2.0.0", "init", "run")
        guide = _compat().generate_migration_guide(old, new)
        self.assertIn("Unchanged", guide)


if __name__ == "__main__":
    unittest.main()
