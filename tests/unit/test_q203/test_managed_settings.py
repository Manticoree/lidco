"""Tests for ManagedSettingsLoader."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from lidco.enterprise.managed_settings import (
    ManagedSettingsError,
    ManagedSettingsLoader,
    SettingsSource,
)


class TestSettingsSource(unittest.TestCase):
    def test_frozen_dataclass(self):
        s = SettingsSource(path="/a.json", data={"k": 1})
        self.assertEqual(s.path, "/a.json")
        self.assertEqual(s.priority, 0)
        self.assertEqual(s.source_type, "file")
        with self.assertRaises(AttributeError):
            s.path = "/b.json"  # type: ignore[misc]


class TestLoadFile(unittest.TestCase):
    def test_load_valid_json(self, tmp_path=None):
        import tempfile, os
        d = tempfile.mkdtemp()
        p = Path(d) / "settings.json"
        p.write_text(json.dumps({"a": 1, "b": {"c": 2}}), encoding="utf-8")
        loader = ManagedSettingsLoader(base_dir=d)
        data = loader.load_file(p)
        self.assertEqual(data, {"a": 1, "b": {"c": 2}})

    def test_load_invalid_json(self):
        import tempfile
        d = tempfile.mkdtemp()
        p = Path(d) / "bad.json"
        p.write_text("not json", encoding="utf-8")
        loader = ManagedSettingsLoader(base_dir=d)
        with self.assertRaises(ManagedSettingsError):
            loader.load_file(p)

    def test_load_nonexistent(self):
        import tempfile
        d = tempfile.mkdtemp()
        loader = ManagedSettingsLoader(base_dir=d)
        with self.assertRaises(ManagedSettingsError):
            loader.load_file(Path(d) / "nope.json")


class TestLoadDirectory(unittest.TestCase):
    def test_load_sorted_by_name(self):
        import tempfile
        d = tempfile.mkdtemp()
        sub = Path(d) / "conf.d"
        sub.mkdir()
        (sub / "02_second.json").write_text(json.dumps({"x": 2}), encoding="utf-8")
        (sub / "01_first.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
        loader = ManagedSettingsLoader(base_dir=d)
        sources = loader.load_directory(sub)
        self.assertEqual(len(sources), 2)
        self.assertIn("01_first", sources[0].path)
        self.assertIn("02_second", sources[1].path)

    def test_load_empty_dir(self):
        import tempfile
        d = tempfile.mkdtemp()
        sub = Path(d) / "empty"
        sub.mkdir()
        loader = ManagedSettingsLoader(base_dir=d)
        self.assertEqual(loader.load_directory(sub), [])

    def test_load_nonexistent_dir(self):
        import tempfile
        d = tempfile.mkdtemp()
        loader = ManagedSettingsLoader(base_dir=d)
        self.assertEqual(loader.load_directory(Path(d) / "nope"), [])


class TestMerge(unittest.TestCase):
    def test_higher_priority_wins(self):
        loader = ManagedSettingsLoader()
        s1 = SettingsSource(path="a", data={"x": 1, "y": 10}, priority=0)
        s2 = SettingsSource(path="b", data={"x": 2}, priority=1)
        merged = loader.merge([s1, s2])
        self.assertEqual(merged["x"], 2)
        self.assertEqual(merged["y"], 10)

    def test_deep_merge(self):
        loader = ManagedSettingsLoader()
        s1 = SettingsSource(path="a", data={"nested": {"a": 1, "b": 2}}, priority=0)
        s2 = SettingsSource(path="b", data={"nested": {"b": 99}}, priority=1)
        merged = loader.merge([s1, s2])
        self.assertEqual(merged["nested"]["a"], 1)
        self.assertEqual(merged["nested"]["b"], 99)


class TestDotNotationGet(unittest.TestCase):
    def test_get_nested(self):
        loader = ManagedSettingsLoader()
        loader.merge([SettingsSource(path="a", data={"a": {"b": {"c": 42}}})])
        self.assertEqual(loader.get("a.b.c"), 42)

    def test_get_default(self):
        loader = ManagedSettingsLoader()
        loader.merge([SettingsSource(path="a", data={})])
        self.assertEqual(loader.get("missing", "default"), "default")


class TestLoadManaged(unittest.TestCase):
    def test_load_managed_with_dir(self):
        import tempfile
        d = tempfile.mkdtemp()
        main = Path(d) / "managed-settings.json"
        main.write_text(json.dumps({"base": True, "x": 0}), encoding="utf-8")
        sub = Path(d) / "managed-settings.d"
        sub.mkdir()
        (sub / "override.json").write_text(json.dumps({"x": 99}), encoding="utf-8")
        loader = ManagedSettingsLoader(base_dir=d)
        data = loader.load_managed()
        self.assertTrue(data["base"])
        self.assertEqual(data["x"], 99)


if __name__ == "__main__":
    unittest.main()
