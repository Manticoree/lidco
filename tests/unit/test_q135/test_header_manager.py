"""Tests for Q135 HeaderManager."""
from __future__ import annotations
import unittest
from lidco.network.header_manager import HeaderManager, Header


class TestHeader(unittest.TestCase):
    def test_creation(self):
        h = Header(name="Content-Type", value="text/plain")
        self.assertEqual(h.name, "Content-Type")
        self.assertEqual(h.value, "text/plain")

    def test_frozen(self):
        h = Header(name="X", value="Y")
        with self.assertRaises(AttributeError):
            h.name = "Z"  # type: ignore[misc]


class TestHeaderManager(unittest.TestCase):
    def setUp(self):
        self.mgr = HeaderManager()

    def test_set_and_get(self):
        self.mgr.set("Content-Type", "text/html")
        self.assertEqual(self.mgr.get("Content-Type"), "text/html")

    def test_case_insensitive_get(self):
        self.mgr.set("Content-Type", "text/html")
        self.assertEqual(self.mgr.get("content-type"), "text/html")
        self.assertEqual(self.mgr.get("CONTENT-TYPE"), "text/html")

    def test_get_missing(self):
        self.assertIsNone(self.mgr.get("X-Missing"))

    def test_has_true(self):
        self.mgr.set("Accept", "json")
        self.assertTrue(self.mgr.has("accept"))

    def test_has_false(self):
        self.assertFalse(self.mgr.has("X-Nope"))

    def test_remove_existing(self):
        self.mgr.set("X-Temp", "1")
        self.assertTrue(self.mgr.remove("x-temp"))
        self.assertIsNone(self.mgr.get("X-Temp"))

    def test_remove_missing(self):
        self.assertFalse(self.mgr.remove("X-Nope"))

    def test_to_dict(self):
        self.mgr.set("A", "1")
        self.mgr.set("B", "2")
        d = self.mgr.to_dict()
        self.assertEqual(d["A"], "1")
        self.assertEqual(d["B"], "2")

    def test_from_dict(self):
        mgr = HeaderManager.from_dict({"X-Custom": "val"})
        self.assertEqual(mgr.get("x-custom"), "val")

    def test_from_dict_roundtrip(self):
        self.mgr.set("K", "V")
        d = self.mgr.to_dict()
        mgr2 = HeaderManager.from_dict(d)
        self.assertEqual(mgr2.get("k"), "V")

    def test_merge(self):
        other = HeaderManager()
        other.set("X-New", "yes")
        self.mgr.set("X-Old", "1")
        self.mgr.merge(other)
        self.assertEqual(self.mgr.get("X-New"), "yes")
        self.assertEqual(self.mgr.get("X-Old"), "1")

    def test_merge_override(self):
        self.mgr.set("Key", "old")
        other = HeaderManager()
        other.set("Key", "new")
        self.mgr.merge(other)
        self.assertEqual(self.mgr.get("Key"), "new")

    def test_set_content_type(self):
        self.mgr.set_content_type()
        self.assertEqual(self.mgr.get("Content-Type"), "application/json")

    def test_set_content_type_custom(self):
        self.mgr.set_content_type("text/xml")
        self.assertEqual(self.mgr.get("content-type"), "text/xml")

    def test_set_authorization(self):
        self.mgr.set_authorization("Bearer abc")
        self.assertEqual(self.mgr.get("Authorization"), "Bearer abc")

    def test_set_accept(self):
        self.mgr.set_accept()
        self.assertEqual(self.mgr.get("Accept"), "application/json")

    def test_len(self):
        self.assertEqual(len(self.mgr), 0)
        self.mgr.set("A", "1")
        self.assertEqual(len(self.mgr), 1)

    def test_repr(self):
        self.mgr.set("X", "1")
        r = repr(self.mgr)
        self.assertIn("HeaderManager", r)


if __name__ == "__main__":
    unittest.main()
