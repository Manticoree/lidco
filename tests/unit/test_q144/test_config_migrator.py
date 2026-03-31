"""Tests for Q144 ConfigMigrator."""
from __future__ import annotations

import unittest

from lidco.config.config_migrator import ConfigMigrator, MigrationStep, MigrationResult
from lidco.config.config_version import ConfigVersion


class TestMigrationStep(unittest.TestCase):
    def test_fields(self):
        step = MigrationStep("1.0.0", "1.1.0", "add x", lambda d: d)
        self.assertEqual(step.from_version, "1.0.0")
        self.assertEqual(step.to_version, "1.1.0")
        self.assertEqual(step.description, "add x")


class TestMigrationResult(unittest.TestCase):
    def test_defaults(self):
        r = MigrationResult(success=True, from_version="1.0.0", to_version="2.0.0", steps_applied=1, data={})
        self.assertEqual(r.errors, [])

    def test_with_errors(self):
        r = MigrationResult(success=False, from_version="1.0.0", to_version="2.0.0", steps_applied=0, data={}, errors=["fail"])
        self.assertEqual(r.errors, ["fail"])


class TestConfigMigrator(unittest.TestCase):
    def setUp(self):
        self.m = ConfigMigrator()

    def _add_chain(self):
        """Add a 1.0.0 -> 1.1.0 -> 2.0.0 chain."""
        self.m.add_step("1.0.0", "1.1.0", "add field_x", lambda d: {**d, "field_x": True})
        self.m.add_step("1.1.0", "2.0.0", "rename a to b", lambda d: {**{k: v for k, v in d.items() if k != "a"}, "b": d.get("a")})

    # --- add_step ---

    def test_add_step(self):
        self.m.add_step("1.0.0", "1.1.0", "desc", lambda d: d)
        self.assertEqual(len(self.m._steps), 1)

    # --- migration_path ---

    def test_path_direct(self):
        self.m.add_step("1.0.0", "2.0.0", "big jump", lambda d: d)
        path = self.m.migration_path("1.0.0", "2.0.0")
        self.assertEqual(len(path), 1)

    def test_path_chain(self):
        self._add_chain()
        path = self.m.migration_path("1.0.0", "2.0.0")
        self.assertEqual(len(path), 2)
        self.assertEqual(path[0].from_version, "1.0.0")
        self.assertEqual(path[1].to_version, "2.0.0")

    def test_path_not_found(self):
        self.m.add_step("1.0.0", "1.1.0", "x", lambda d: d)
        path = self.m.migration_path("1.0.0", "3.0.0")
        self.assertEqual(path, [])

    def test_path_same_version(self):
        path = self.m.migration_path("1.0.0", "1.0.0")
        self.assertEqual(path, [])

    # --- can_migrate ---

    def test_can_migrate_true(self):
        self._add_chain()
        self.assertTrue(self.m.can_migrate("1.0.0", "2.0.0"))

    def test_can_migrate_false(self):
        self.assertFalse(self.m.can_migrate("1.0.0", "9.0.0"))

    def test_can_migrate_same_version(self):
        self.assertTrue(self.m.can_migrate("1.0.0", "1.0.0"))

    # --- migrate ---

    def test_migrate_success(self):
        self._add_chain()
        data = {ConfigVersion.VERSION_KEY: "1.0.0", "a": 42}
        result = self.m.migrate(data, "2.0.0")
        self.assertTrue(result.success)
        self.assertEqual(result.steps_applied, 2)
        self.assertEqual(result.from_version, "1.0.0")
        self.assertEqual(result.to_version, "2.0.0")
        self.assertTrue(result.data.get("field_x"))
        self.assertEqual(result.data[ConfigVersion.VERSION_KEY], "2.0.0")

    def test_migrate_no_version_defaults_to_000(self):
        self.m.add_step("0.0.0", "1.0.0", "init", lambda d: {**d, "init": True})
        result = self.m.migrate({"x": 1}, "1.0.0")
        self.assertTrue(result.success)
        self.assertEqual(result.from_version, "0.0.0")

    def test_migrate_already_at_target(self):
        data = {ConfigVersion.VERSION_KEY: "1.0.0"}
        result = self.m.migrate(data, "1.0.0")
        self.assertTrue(result.success)
        self.assertEqual(result.steps_applied, 0)

    def test_migrate_no_path(self):
        data = {ConfigVersion.VERSION_KEY: "1.0.0"}
        result = self.m.migrate(data, "9.0.0")
        self.assertFalse(result.success)
        self.assertGreater(len(result.errors), 0)

    def test_migrate_step_error(self):
        def bad(d):
            raise RuntimeError("boom")
        self.m.add_step("1.0.0", "2.0.0", "fail step", bad)
        data = {ConfigVersion.VERSION_KEY: "1.0.0"}
        result = self.m.migrate(data, "2.0.0")
        self.assertFalse(result.success)
        self.assertEqual(result.steps_applied, 0)
        self.assertIn("boom", result.errors[0])

    # --- dry_run ---

    def test_dry_run_does_not_modify_original(self):
        self._add_chain()
        data = {ConfigVersion.VERSION_KEY: "1.0.0", "a": 42}
        original = dict(data)
        result = self.m.dry_run(data, "2.0.0")
        self.assertTrue(result.success)
        self.assertEqual(data, original)

    def test_dry_run_returns_result(self):
        self._add_chain()
        data = {ConfigVersion.VERSION_KEY: "1.0.0", "a": 42}
        result = self.m.dry_run(data, "2.0.0")
        self.assertEqual(result.steps_applied, 2)


if __name__ == "__main__":
    unittest.main()
