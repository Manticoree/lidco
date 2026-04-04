"""Tests for MarkerRegistry."""
from __future__ import annotations

import unittest

from lidco.annotations.markers import Marker, MarkerRegistry


class TestMarker(unittest.TestCase):
    def test_frozen(self):
        m = Marker(name="X", prefix="X")
        with self.assertRaises(AttributeError):
            m.name = "Y"  # type: ignore[misc]

    def test_defaults(self):
        m = Marker(name="A", prefix="A")
        self.assertEqual(m.priority, 0)
        self.assertEqual(m.color, "")
        self.assertEqual(m.description, "")


class TestMarkerRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = MarkerRegistry()

    def test_builtin_names(self):
        names = self.reg.builtin_names()
        self.assertIn("TODO", names)
        self.assertIn("FIXME", names)
        self.assertIn("NOTE", names)
        self.assertEqual(len(names), 6)

    def test_get_builtin(self):
        m = self.reg.get("TODO")
        self.assertIsNotNone(m)
        self.assertEqual(m.priority, 2)

    def test_register_custom(self):
        m = Marker(name="HACK", prefix="HACK", priority=1)
        self.reg.register(m)
        self.assertEqual(self.reg.get("HACK"), m)

    def test_remove_custom(self):
        self.reg.register(Marker(name="HACK", prefix="HACK"))
        self.assertTrue(self.reg.remove("HACK"))
        self.assertIsNone(self.reg.get("HACK"))

    def test_remove_builtin_fails(self):
        self.assertFalse(self.reg.remove("TODO"))
        self.assertIsNotNone(self.reg.get("TODO"))

    def test_remove_nonexistent(self):
        self.assertFalse(self.reg.remove("NOPE"))

    def test_all_markers_sorted(self):
        markers = self.reg.all_markers()
        priorities = [m.priority for m in markers]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_by_priority(self):
        result = self.reg.by_priority(min_priority=2)
        for m in result:
            self.assertGreaterEqual(m.priority, 2)

    def test_scan_text_finds_todo(self):
        text = "line1\n# TODO: fix this\nline3"
        hits = self.reg.scan_text(text)
        self.assertTrue(any(h["marker"] == "TODO" for h in hits))
        self.assertEqual(hits[0]["text"], "fix this")

    def test_scan_text_finds_multiple(self):
        text = "TODO: a\nFIXME: b\nNOTE: c"
        hits = self.reg.scan_text(text)
        markers_found = {h["marker"] for h in hits}
        self.assertIn("TODO", markers_found)
        self.assertIn("FIXME", markers_found)
        self.assertIn("NOTE", markers_found)

    def test_scan_text_empty(self):
        self.assertEqual(self.reg.scan_text("no markers here"), [])

    def test_summary(self):
        s = self.reg.summary()
        self.assertEqual(s["builtin"], 6)
        self.assertEqual(s["custom"], 0)
        self.assertIn("FIXME", s["markers"])


if __name__ == "__main__":
    unittest.main()
