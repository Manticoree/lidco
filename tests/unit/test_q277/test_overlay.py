"""Tests for AnnotationOverlay."""
from __future__ import annotations

import unittest

from lidco.annotations.engine import AnnotationEngine
from lidco.annotations.markers import MarkerRegistry
from lidco.annotations.overlay import AnnotationOverlay, OverlayLine


class TestOverlayLine(unittest.TestCase):
    def test_defaults(self):
        ol = OverlayLine(line_number=1, content="x")
        self.assertEqual(ol.annotations, [])
        self.assertEqual(ol.gutter_icon, "")


class TestAnnotationOverlay(unittest.TestCase):
    def setUp(self):
        self.engine = AnnotationEngine()
        self.markers = MarkerRegistry()
        self.overlay = AnnotationOverlay(self.engine, self.markers)
        self.code = ["line1", "line2", "line3", "line4"]

    def test_render_no_annotations(self):
        lines = self.overlay.render("f.py", self.code)
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0].content, "line1")
        self.assertEqual(lines[0].gutter_icon, "")

    def test_render_with_annotation(self):
        self.engine.add("f.py", 2, "check this", category="warning")
        lines = self.overlay.render("f.py", self.code)
        self.assertEqual(len(lines[1].annotations), 1)
        self.assertIn("warning", lines[1].annotations[0])
        self.assertEqual(lines[1].gutter_icon, "[!]")

    def test_render_text(self):
        self.engine.add("f.py", 1, "note here")
        text = self.overlay.render_text("f.py", self.code)
        self.assertIn("line1", text)
        self.assertIn("note here", text)

    def test_filter_by_category(self):
        self.engine.add("f.py", 1, "a", category="warning")
        self.engine.add("f.py", 3, "b", category="note")
        result = self.overlay.filter_by_category("f.py", self.code, "warning")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].line_number, 1)

    def test_gutter_icon_for(self):
        self.assertEqual(self.overlay.gutter_icon_for("warning"), "[!]")
        self.assertEqual(self.overlay.gutter_icon_for("note"), "[i]")
        self.assertEqual(self.overlay.gutter_icon_for("unknown"), "[*]")

    def test_summary(self):
        s = self.overlay.summary()
        self.assertEqual(s["engine_count"], 0)
        self.assertTrue(s["has_markers"])

    def test_summary_no_markers(self):
        overlay = AnnotationOverlay(self.engine)
        s = overlay.summary()
        self.assertFalse(s["has_markers"])


if __name__ == "__main__":
    unittest.main()
