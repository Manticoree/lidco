"""Tests for TeamTemplateRegistry."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from lidco.templates.team_registry import (
    ConflictError,
    ConflictStrategy,
    ImportResult,
    RegistryError,
    TeamTemplateRegistry,
    TemplateEntry,
    TemplateNotFoundError,
    _compute_checksum,
)


class TestComputeChecksum(unittest.TestCase):
    def test_deterministic(self):
        data = {"name": "test", "value": 42}
        c1 = _compute_checksum(data)
        c2 = _compute_checksum(data)
        self.assertEqual(c1, c2)
        self.assertEqual(len(c1), 12)

    def test_different_data(self):
        c1 = _compute_checksum({"a": 1})
        c2 = _compute_checksum({"a": 2})
        self.assertNotEqual(c1, c2)


class TestTeamTemplateRegistryCRUD(unittest.TestCase):
    def test_add_and_get(self):
        reg = TeamTemplateRegistry()
        entry = reg.add("tpl1", {"hello": "world"}, version="1.0", author="dev")
        self.assertEqual(entry.name, "tpl1")
        self.assertEqual(entry.version, "1.0")
        self.assertIsNotNone(reg.get("tpl1"))

    def test_remove(self):
        reg = TeamTemplateRegistry()
        reg.add("tpl1", {"hello": "world"})
        self.assertTrue(reg.remove("tpl1"))
        self.assertFalse(reg.remove("tpl1"))
        self.assertIsNone(reg.get("tpl1"))

    def test_list_entries(self):
        reg = TeamTemplateRegistry()
        reg.add("a", {"x": 1})
        reg.add("b", {"y": 2})
        self.assertEqual(len(reg.list_entries()), 2)
        self.assertEqual(reg.count, 2)

    def test_search(self):
        reg = TeamTemplateRegistry()
        reg.add("python-starter", {})
        reg.add("node-starter", {})
        reg.add("go-api", {})
        results = reg.search("starter")
        self.assertEqual(len(results), 2)


class TestTeamTemplateRegistryVersioning(unittest.TestCase):
    def test_history_on_update(self):
        reg = TeamTemplateRegistry()
        reg.add("tpl", {"v": 1}, version="1.0")
        reg.add("tpl", {"v": 2}, version="2.0")
        history = reg.get_history("tpl")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].version, "1.0")

    def test_get_version(self):
        reg = TeamTemplateRegistry()
        reg.add("tpl", {"v": 1}, version="1.0")
        reg.add("tpl", {"v": 2}, version="2.0")
        old = reg.get_version("tpl", "1.0")
        self.assertIsNotNone(old)
        self.assertEqual(old.data, {"v": 1})
        current = reg.get_version("tpl", "2.0")
        self.assertIsNotNone(current)


class TestTeamTemplateRegistryImportExport(unittest.TestCase):
    def test_export_and_import(self):
        reg = TeamTemplateRegistry()
        reg.add("alpha", {"x": 1}, version="1.0")
        reg.add("beta", {"y": 2}, version="1.0")
        exported = reg.export_all()

        reg2 = TeamTemplateRegistry()
        result = reg2.import_entries(exported)
        self.assertEqual(len(result.imported), 2)
        self.assertEqual(reg2.count, 2)

    def test_import_skip_strategy(self):
        reg = TeamTemplateRegistry()
        reg.add("alpha", {"x": 1})
        exported = reg.export_all()
        # Change data so checksums differ
        exported["entries"][0]["data"] = {"x": 999}
        result = reg.import_entries(exported, strategy=ConflictStrategy.SKIP)
        self.assertIn("alpha", result.skipped)

    def test_import_overwrite_strategy(self):
        reg = TeamTemplateRegistry()
        reg.add("alpha", {"x": 1})
        exported = reg.export_all()
        exported["entries"][0]["data"] = {"x": 999}
        result = reg.import_entries(exported, strategy=ConflictStrategy.OVERWRITE)
        self.assertIn("alpha", result.imported)
        self.assertEqual(reg.get("alpha").data, {"x": 999})

    def test_import_rename_strategy(self):
        reg = TeamTemplateRegistry()
        reg.add("alpha", {"x": 1})
        exported = reg.export_all()
        exported["entries"][0]["data"] = {"x": 999}
        result = reg.import_entries(exported, strategy=ConflictStrategy.RENAME)
        self.assertIn("alpha_imported", result.imported)
        self.assertIn("alpha", result.conflicts)

    def test_import_error_strategy(self):
        reg = TeamTemplateRegistry()
        reg.add("alpha", {"x": 1})
        exported = reg.export_all()
        exported["entries"][0]["data"] = {"x": 999}
        result = reg.import_entries(exported, strategy=ConflictStrategy.ERROR)
        self.assertIn("alpha", result.conflicts)


class TestTeamTemplateRegistryPersistence(unittest.TestCase):
    def test_save_and_load(self, tmp_path=None):
        """Test save/load round-trip using a temp directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            reg = TeamTemplateRegistry(storage_dir=path)
            reg.add("tpl1", {"a": 1}, version="1.0")
            reg.add("tpl2", {"b": 2}, version="2.0")
            saved_path = reg.save()
            self.assertTrue(Path(saved_path).exists())

            reg2 = TeamTemplateRegistry(storage_dir=path)
            loaded = reg2.load()
            self.assertEqual(loaded, 2)
            self.assertEqual(reg2.count, 2)

    def test_save_no_path_raises(self):
        reg = TeamTemplateRegistry()
        with self.assertRaises(RegistryError):
            reg.save()


if __name__ == "__main__":
    unittest.main()
