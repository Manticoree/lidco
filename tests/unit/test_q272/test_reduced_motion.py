"""Tests for ReducedMotion (Q272)."""
from __future__ import annotations

import unittest

from lidco.a11y.reduced_motion import MotionPreference, ReducedMotion


class TestMotionPreference(unittest.TestCase):
    def test_defaults(self):
        mp = MotionPreference()
        self.assertTrue(mp.animations)
        self.assertTrue(mp.spinners)
        self.assertTrue(mp.transitions)
        self.assertTrue(mp.scroll_smooth)


class TestEnable(unittest.TestCase):
    def test_enable_returns_all_off(self):
        rm = ReducedMotion()
        prefs = rm.enable()
        self.assertFalse(prefs.animations)
        self.assertFalse(prefs.spinners)
        self.assertFalse(prefs.transitions)
        self.assertFalse(prefs.scroll_smooth)
        self.assertTrue(rm.is_enabled())


class TestDisable(unittest.TestCase):
    def test_disable_returns_defaults(self):
        rm = ReducedMotion(enabled=True)
        prefs = rm.disable()
        self.assertTrue(prefs.animations)
        self.assertTrue(prefs.spinners)
        self.assertFalse(rm.is_enabled())


class TestPreferences(unittest.TestCase):
    def test_returns_copy(self):
        rm = ReducedMotion()
        p1 = rm.preferences()
        p2 = rm.preferences()
        self.assertEqual(p1, p2)
        self.assertIsNot(p1, p2)


class TestSetPreference(unittest.TestCase):
    def test_valid_key(self):
        rm = ReducedMotion()
        p = rm.set_preference("animations", False)
        self.assertFalse(p.animations)

    def test_invalid_key_raises(self):
        rm = ReducedMotion()
        with self.assertRaises(ValueError):
            rm.set_preference("nonexistent", True)


class TestShouldAnimate(unittest.TestCase):
    def test_false_when_enabled(self):
        rm = ReducedMotion(enabled=True)
        self.assertFalse(rm.should_animate())

    def test_true_when_disabled(self):
        rm = ReducedMotion(enabled=False)
        self.assertTrue(rm.should_animate())


class TestProgressStyle(unittest.TestCase):
    def test_static_when_enabled(self):
        rm = ReducedMotion(enabled=True)
        self.assertEqual(rm.progress_style(), "static")

    def test_animated_when_disabled(self):
        rm = ReducedMotion()
        self.assertEqual(rm.progress_style(), "animated")


if __name__ == "__main__":
    unittest.main()
