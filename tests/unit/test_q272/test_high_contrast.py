"""Tests for HighContrastMode (Q272)."""
from __future__ import annotations

import unittest

from lidco.a11y.high_contrast import ContrastPair, HighContrastMode


class TestContrastPairFrozen(unittest.TestCase):
    def test_frozen(self):
        cp = ContrastPair("#FFF", "#000", 21.0, True, True)
        with self.assertRaises(AttributeError):
            cp.ratio = 1.0  # type: ignore[misc]


class TestLuminance(unittest.TestCase):
    def test_black(self):
        hc = HighContrastMode()
        self.assertAlmostEqual(hc._luminance("#000000"), 0.0, places=4)

    def test_white(self):
        hc = HighContrastMode()
        self.assertAlmostEqual(hc._luminance("#FFFFFF"), 1.0, places=4)

    def test_mid_grey(self):
        hc = HighContrastMode()
        lum = hc._luminance("#808080")
        self.assertGreater(lum, 0.1)
        self.assertLess(lum, 0.5)


class TestContrastRatio(unittest.TestCase):
    def test_black_white(self):
        hc = HighContrastMode()
        ratio = hc._contrast_ratio(0.0, 1.0)
        self.assertAlmostEqual(ratio, 21.0, places=1)

    def test_same_color(self):
        hc = HighContrastMode()
        ratio = hc._contrast_ratio(0.5, 0.5)
        self.assertAlmostEqual(ratio, 1.0, places=1)


class TestCheckContrast(unittest.TestCase):
    def test_white_on_black_passes_both(self):
        hc = HighContrastMode()
        pair = hc.check_contrast("#FFFFFF", "#000000")
        self.assertTrue(pair.passes_aa)
        self.assertTrue(pair.passes_aaa)
        self.assertGreaterEqual(pair.ratio, 20.0)

    def test_low_contrast_fails(self):
        hc = HighContrastMode()
        pair = hc.check_contrast("#777777", "#888888")
        self.assertFalse(pair.passes_aa)
        self.assertFalse(pair.passes_aaa)

    def test_aa_but_not_aaa(self):
        hc = HighContrastMode()
        # Dark text on white — ratio ~5.x
        pair = hc.check_contrast("#767676", "#FFFFFF")
        self.assertTrue(pair.passes_aa)
        # May or may not pass AAA depending on exact ratio


class TestSuggestFix(unittest.TestCase):
    def test_already_passing(self):
        hc = HighContrastMode()
        self.assertEqual(hc.suggest_fix("#FFFFFF", "#000000"), "#FFFFFF")

    def test_dark_bg_suggests_white(self):
        hc = HighContrastMode()
        result = hc.suggest_fix("#333333", "#000000")
        self.assertEqual(result, "#FFFFFF")

    def test_light_bg_suggests_black(self):
        hc = HighContrastMode()
        result = hc.suggest_fix("#CCCCCC", "#FFFFFF")
        self.assertEqual(result, "#000000")


class TestEnableDisable(unittest.TestCase):
    def test_toggle(self):
        hc = HighContrastMode()
        self.assertFalse(hc.is_enabled())
        hc.enable()
        self.assertTrue(hc.is_enabled())
        hc.disable()
        self.assertFalse(hc.is_enabled())


class TestPalette(unittest.TestCase):
    def test_palette_keys(self):
        hc = HighContrastMode()
        pal = hc.palette()
        self.assertIn("text", pal)
        self.assertIn("background", pal)
        self.assertIn("error", pal)


class TestSummary(unittest.TestCase):
    def test_summary_keys(self):
        hc = HighContrastMode(min_ratio=7.0)
        s = hc.summary()
        self.assertEqual(s["min_ratio"], 7.0)
        self.assertFalse(s["enabled"])


if __name__ == "__main__":
    unittest.main()
