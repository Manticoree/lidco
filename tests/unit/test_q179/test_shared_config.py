"""Tests for SharedConfigResolver."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from lidco.workspace.shared_config import SharedConfigResolver


class TestSharedConfigResolver(unittest.TestCase):
    """Tests for workspace/package config merging."""

    def setUp(self) -> None:
        self.resolver = SharedConfigResolver()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.ws = os.path.join(self.root, "workspace")
        self.pkg = os.path.join(self.root, "workspace", "packages", "core")
        os.makedirs(self.ws, exist_ok=True)
        os.makedirs(self.pkg, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- helpers -------------------------------------------------------------

    def _write_config(self, base: str, data: dict) -> None:
        cfg_dir = os.path.join(base, ".lidco")
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, "config.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    # -- workspace only ------------------------------------------------------

    def test_workspace_only(self) -> None:
        self._write_config(self.ws, {"key": "ws_value"})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["key"], "ws_value")

    def test_package_only(self) -> None:
        self._write_config(self.pkg, {"key": "pkg_value"})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["key"], "pkg_value")

    # -- merging -------------------------------------------------------------

    def test_package_overrides_workspace(self) -> None:
        self._write_config(self.ws, {"key": "ws"})
        self._write_config(self.pkg, {"key": "pkg"})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["key"], "pkg")

    def test_both_keys_preserved(self) -> None:
        self._write_config(self.ws, {"a": 1})
        self._write_config(self.pkg, {"b": 2})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 2)

    def test_deep_merge_nested(self) -> None:
        self._write_config(self.ws, {"nested": {"x": 1, "y": 2}})
        self._write_config(self.pkg, {"nested": {"y": 99, "z": 3}})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["nested"]["x"], 1)
        self.assertEqual(result["nested"]["y"], 99)
        self.assertEqual(result["nested"]["z"], 3)

    def test_deep_merge_override_dict_with_scalar(self) -> None:
        self._write_config(self.ws, {"key": {"a": 1}})
        self._write_config(self.pkg, {"key": "scalar"})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["key"], "scalar")

    # -- missing configs -----------------------------------------------------

    def test_no_configs(self) -> None:
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result, {})

    def test_missing_workspace_dir(self) -> None:
        self._write_config(self.pkg, {"key": "val"})
        result = self.resolver.resolve("/nonexistent_xyz", self.pkg)
        self.assertEqual(result["key"], "val")

    def test_malformed_json(self) -> None:
        cfg_dir = os.path.join(self.ws, ".lidco")
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, "config.json"), "w") as fh:
            fh.write("not json{{{")
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result, {})

    def test_non_dict_json(self) -> None:
        cfg_dir = os.path.join(self.ws, ".lidco")
        os.makedirs(cfg_dir, exist_ok=True)
        with open(os.path.join(cfg_dir, "config.json"), "w") as fh:
            json.dump([1, 2, 3], fh)
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result, {})

    # -- relative path resolution --------------------------------------------

    def test_resolve_relative_path_from_workspace(self) -> None:
        self._write_config(self.ws, {"output": "build/dist"})
        result = self.resolver.resolve(self.ws, self.pkg)
        expected = os.path.normpath(os.path.join(os.path.abspath(self.ws), "build/dist"))
        self.assertEqual(result["output"], expected)

    def test_resolve_relative_path_from_package(self) -> None:
        self._write_config(self.ws, {"output": "build/dist"})
        self._write_config(self.pkg, {"output": "local/out"})
        result = self.resolver.resolve(self.ws, self.pkg)
        expected = os.path.normpath(os.path.join(os.path.abspath(self.pkg), "local/out"))
        self.assertEqual(result["output"], expected)

    def test_absolute_path_unchanged(self) -> None:
        abs_path = os.path.abspath("/tmp/absolute/path")
        self._write_config(self.ws, {"output": abs_path})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["output"], abs_path)

    def test_non_path_string_unchanged(self) -> None:
        self._write_config(self.ws, {"name": "my-project"})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["name"], "my-project")

    # -- misc ----------------------------------------------------------------

    def test_empty_workspace_config(self) -> None:
        self._write_config(self.ws, {})
        self._write_config(self.pkg, {"key": "val"})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["key"], "val")

    def test_empty_package_config(self) -> None:
        self._write_config(self.ws, {"key": "val"})
        self._write_config(self.pkg, {})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["key"], "val")

    def test_numeric_values_preserved(self) -> None:
        self._write_config(self.ws, {"timeout": 30})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["timeout"], 30)

    def test_boolean_values_preserved(self) -> None:
        self._write_config(self.ws, {"debug": True})
        self._write_config(self.pkg, {"debug": False})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertFalse(result["debug"])

    def test_list_values_override(self) -> None:
        self._write_config(self.ws, {"plugins": ["a", "b"]})
        self._write_config(self.pkg, {"plugins": ["c"]})
        result = self.resolver.resolve(self.ws, self.pkg)
        self.assertEqual(result["plugins"], ["c"])


if __name__ == "__main__":
    unittest.main()
