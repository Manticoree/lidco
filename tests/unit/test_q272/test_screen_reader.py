"""Tests for ScreenReaderSupport (Q272)."""
from __future__ import annotations

import unittest

from lidco.a11y.screen_reader import Annotation, Landmark, ScreenReaderSupport


class TestLandmark(unittest.TestCase):
    def test_frozen(self):
        lm = Landmark(id="a", type="main", label="Main")
        with self.assertRaises(AttributeError):
            lm.type = "banner"  # type: ignore[misc]


class TestAnnotation(unittest.TestCase):
    def test_defaults(self):
        ann = Annotation(element_id="e1", role="button", label="OK")
        self.assertEqual(ann.description, "")


class TestAddRemoveLandmark(unittest.TestCase):
    def test_add_valid_types(self):
        sr = ScreenReaderSupport()
        for t in ("banner", "navigation", "main", "complementary", "contentinfo"):
            lm = sr.add_landmark(t, f"Label-{t}")
            self.assertEqual(lm.type, t)

    def test_add_invalid_type_raises(self):
        sr = ScreenReaderSupport()
        with self.assertRaises(ValueError):
            sr.add_landmark("invalid", "bad")

    def test_remove_existing(self):
        sr = ScreenReaderSupport()
        lm = sr.add_landmark("main", "M")
        self.assertTrue(sr.remove_landmark(lm.id))
        self.assertEqual(sr.get_structure(), [])

    def test_remove_missing(self):
        sr = ScreenReaderSupport()
        self.assertFalse(sr.remove_landmark("nope"))


class TestAnnotate(unittest.TestCase):
    def test_annotate_appears_in_render(self):
        sr = ScreenReaderSupport()
        sr.annotate("btn1", "button", "Save", "Saves the document")
        text = sr.render_text()
        self.assertIn("button", text)
        self.assertIn("Save", text)
        self.assertIn("Saves the document", text)


class TestRenderText(unittest.TestCase):
    def test_disabled_returns_empty(self):
        sr = ScreenReaderSupport(enabled=False)
        sr.add_landmark("main", "Main", "content here")
        self.assertEqual(sr.render_text(), "")

    def test_landmarks_and_annotations(self):
        sr = ScreenReaderSupport()
        sr.add_landmark("banner", "Header", "Welcome")
        sr.annotate("x", "link", "Home")
        text = sr.render_text()
        self.assertIn("[banner] Header", text)
        self.assertIn("Welcome", text)
        self.assertIn("(link) Home", text)


class TestEnableDisable(unittest.TestCase):
    def test_toggle(self):
        sr = ScreenReaderSupport(enabled=False)
        self.assertFalse(sr.is_enabled())
        sr.enable()
        self.assertTrue(sr.is_enabled())
        sr.disable()
        self.assertFalse(sr.is_enabled())


class TestSummary(unittest.TestCase):
    def test_summary_keys(self):
        sr = ScreenReaderSupport()
        sr.add_landmark("main", "M")
        sr.annotate("e", "role", "L")
        s = sr.summary()
        self.assertEqual(s["landmarks"], 1)
        self.assertEqual(s["annotations"], 1)
        self.assertTrue(s["enabled"])


if __name__ == "__main__":
    unittest.main()
