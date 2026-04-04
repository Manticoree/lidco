"""Tests for PresetSharing."""
from __future__ import annotations

import json
import unittest

from lidco.presets.library import Preset, PresetLibrary
from lidco.presets.sharing import PresetSharing, SharedPreset, _checksum
from lidco.presets.template import SessionTemplate


class TestPresetSharing(unittest.TestCase):
    def setUp(self):
        self.lib = PresetLibrary()
        self.sharing = PresetSharing(self.lib)

    def test_export_preset(self):
        shared = self.sharing.export_preset("bug-fix")
        self.assertEqual(shared.name, "bug-fix")
        self.assertEqual(shared.author, "system")
        self.assertTrue(shared.shared_at > 0)
        data = json.loads(shared.data)
        self.assertEqual(data["name"], "bug-fix")

    def test_export_missing_raises(self):
        with self.assertRaises(KeyError):
            self.sharing.export_preset("nope")

    def test_verify_valid(self):
        shared = self.sharing.export_preset("feature")
        self.assertTrue(self.sharing.verify(shared))

    def test_verify_invalid(self):
        shared = self.sharing.export_preset("feature")
        tampered = SharedPreset(
            name=shared.name,
            data=shared.data.replace("feature", "hacked"),
            author=shared.author,
            shared_at=shared.shared_at,
            checksum=shared.checksum,
        )
        self.assertFalse(self.sharing.verify(tampered))

    def test_import_new_preset(self):
        # Create a new template, export it, then import into another lib
        t = SessionTemplate(name="new-one", description="New")
        self.lib.add(Preset(name="new-one", category="user", template=t, author="me"))
        shared = self.sharing.export_preset("new-one")
        # Remove it from library
        self.lib.remove("new-one")
        self.assertIsNone(self.lib.get("new-one"))
        # Import
        ok = self.sharing.import_preset(shared)
        self.assertTrue(ok)
        self.assertIsNotNone(self.lib.get("new-one"))

    def test_import_conflict_no_overwrite(self):
        shared = self.sharing.export_preset("bug-fix")
        # bug-fix already exists
        ok = self.sharing.import_preset(shared, overwrite=False)
        self.assertFalse(ok)

    def test_import_conflict_overwrite(self):
        shared = self.sharing.export_preset("bug-fix")
        ok = self.sharing.import_preset(shared, overwrite=True)
        self.assertTrue(ok)

    def test_import_bad_checksum(self):
        shared = SharedPreset(
            name="bad",
            data='{"name":"bad"}',
            author="x",
            shared_at=1.0,
            checksum="wrong",
        )
        ok = self.sharing.import_preset(shared)
        self.assertFalse(ok)

    def test_shared_presets(self):
        self.assertEqual(self.sharing.shared_presets(), [])
        self.sharing.export_preset("bug-fix")
        self.sharing.export_preset("feature")
        self.assertEqual(len(self.sharing.shared_presets()), 2)

    def test_conflicts(self):
        shared = self.sharing.export_preset("bug-fix")
        self.assertTrue(self.sharing.conflicts(shared))
        fake = SharedPreset(name="zzz", data="{}", author="x", shared_at=0, checksum="x")
        self.assertFalse(self.sharing.conflicts(fake))

    def test_summary(self):
        self.sharing.export_preset("docs")
        s = self.sharing.summary()
        self.assertEqual(s["shared_count"], 1)
        self.assertEqual(s["library_total"], 5)


if __name__ == "__main__":
    unittest.main()
