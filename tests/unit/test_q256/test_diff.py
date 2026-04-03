"""Tests for APIDiff (Q256)."""
from __future__ import annotations

import unittest

from lidco.api_intel.diff import APIDiff, DiffEntry
from lidco.api_intel.extractor import Endpoint


class TestDiffEntry(unittest.TestCase):
    def test_frozen(self):
        e = DiffEntry(type="added", path="GET /x", details="new")
        with self.assertRaises(AttributeError):
            e.type = "removed"  # type: ignore[misc]

    def test_defaults(self):
        e = DiffEntry(type="added", path="GET /x", details="new")
        self.assertFalse(e.breaking)


class TestDiffBasic(unittest.TestCase):
    def setUp(self):
        self.differ = APIDiff()

    def test_no_changes(self):
        eps = [Endpoint(method="GET", path="/a")]
        entries = self.differ.diff(eps, eps)
        self.assertEqual(entries, [])

    def test_added_endpoint(self):
        old = [Endpoint(method="GET", path="/a")]
        new = [Endpoint(method="GET", path="/a"), Endpoint(method="POST", path="/b")]
        entries = self.differ.diff(old, new)
        added = [e for e in entries if e.type == "added"]
        self.assertEqual(len(added), 1)
        self.assertIn("POST /b", added[0].path)
        self.assertFalse(added[0].breaking)

    def test_removed_endpoint(self):
        old = [Endpoint(method="GET", path="/a"), Endpoint(method="DELETE", path="/b")]
        new = [Endpoint(method="GET", path="/a")]
        entries = self.differ.diff(old, new)
        removed = [e for e in entries if e.type == "removed"]
        self.assertEqual(len(removed), 1)
        self.assertTrue(removed[0].breaking)

    def test_changed_params_removed(self):
        old = [Endpoint(method="GET", path="/a", params=({"name": "q"},))]
        new = [Endpoint(method="GET", path="/a", params=())]
        entries = self.differ.diff(old, new)
        changed = [e for e in entries if e.type == "changed"]
        self.assertTrue(len(changed) >= 1)
        self.assertTrue(any(e.breaking for e in changed))

    def test_changed_params_added(self):
        old = [Endpoint(method="GET", path="/a", params=())]
        new = [Endpoint(method="GET", path="/a", params=({"name": "q"},))]
        entries = self.differ.diff(old, new)
        changed = [e for e in entries if e.type == "changed"]
        self.assertTrue(len(changed) >= 1)
        self.assertFalse(any(e.breaking for e in changed))

    def test_return_type_change_is_breaking(self):
        old = [Endpoint(method="GET", path="/a", return_type="list")]
        new = [Endpoint(method="GET", path="/a", return_type="dict")]
        entries = self.differ.diff(old, new)
        self.assertTrue(any(e.breaking for e in entries))

    def test_description_change_not_breaking(self):
        old = [Endpoint(method="GET", path="/a", description="old")]
        new = [Endpoint(method="GET", path="/a", description="new")]
        entries = self.differ.diff(old, new)
        desc_changes = [e for e in entries if "Description" in e.details]
        self.assertTrue(len(desc_changes) >= 1)
        self.assertFalse(any(e.breaking for e in desc_changes))


class TestBreakingChanges(unittest.TestCase):
    def test_filter(self):
        entries = [
            DiffEntry(type="removed", path="GET /a", details="gone", breaking=True),
            DiffEntry(type="added", path="POST /b", details="new", breaking=False),
        ]
        breaking = APIDiff.breaking_changes(entries)
        self.assertEqual(len(breaking), 1)
        self.assertEqual(breaking[0].path, "GET /a")


class TestSummary(unittest.TestCase):
    def test_no_changes(self):
        self.assertEqual(APIDiff.summary([]), "No changes detected.")

    def test_with_changes(self):
        entries = [
            DiffEntry(type="added", path="POST /b", details="new", breaking=False),
            DiffEntry(type="removed", path="GET /a", details="gone", breaking=True),
        ]
        s = APIDiff.summary(entries)
        self.assertIn("2 change(s)", s)
        self.assertIn("1 breaking", s)
        self.assertIn("[BREAKING]", s)


class TestIsCompatible(unittest.TestCase):
    def setUp(self):
        self.differ = APIDiff()

    def test_compatible(self):
        old = [Endpoint(method="GET", path="/a")]
        new = [Endpoint(method="GET", path="/a"), Endpoint(method="POST", path="/b")]
        self.assertTrue(self.differ.is_compatible(old, new))

    def test_incompatible(self):
        old = [Endpoint(method="GET", path="/a")]
        new = []
        self.assertFalse(self.differ.is_compatible(old, new))

    def test_empty_both(self):
        self.assertTrue(self.differ.is_compatible([], []))


if __name__ == "__main__":
    unittest.main()
