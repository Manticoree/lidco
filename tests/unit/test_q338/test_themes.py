"""Tests for ThemeGallery (Task 1803)."""
from __future__ import annotations

import unittest

from lidco.community.themes import Theme, ThemeColors, ThemeGallery, ThemeSeason


def _theme(name: str = "dark-mode", **kw) -> Theme:
    defaults = dict(author="alice", description="A dark theme")
    defaults.update(kw)
    return Theme(name=name, **defaults)


class TestThemeColors(unittest.TestCase):
    def test_defaults(self):
        c = ThemeColors()
        self.assertEqual(c.primary, "#007acc")
        self.assertIn("background", c.to_dict())

    def test_custom(self):
        c = ThemeColors(primary="#ff0000")
        self.assertEqual(c.primary, "#ff0000")


class TestTheme(unittest.TestCase):
    def test_defaults(self):
        t = _theme()
        self.assertEqual(t.name, "dark-mode")
        self.assertEqual(t.season, ThemeSeason.NONE)
        self.assertEqual(t.average_rating, 0.0)
        self.assertEqual(t.installs, 0)

    def test_rate(self):
        t = _theme()
        t2 = t.rate(4)
        self.assertEqual(t.rating_count, 0)
        self.assertEqual(t2.rating_count, 1)
        self.assertAlmostEqual(t2.average_rating, 4.0)

    def test_rate_invalid(self):
        t = _theme()
        with self.assertRaises(ValueError):
            t.rate(0)
        with self.assertRaises(ValueError):
            t.rate(6)

    def test_install(self):
        t = _theme()
        t2 = t.install()
        self.assertEqual(t.installs, 0)
        self.assertEqual(t2.installs, 1)

    def test_preview(self):
        t = _theme()
        p = t.preview()
        self.assertEqual(p["name"], "dark-mode")
        self.assertIn("colors", p)

    def test_to_dict(self):
        t = _theme(tags=["minimal"])
        d = t.to_dict()
        self.assertEqual(d["tags"], ["minimal"])
        self.assertEqual(d["season"], "none")


class TestThemeGallery(unittest.TestCase):
    def setUp(self):
        self.g = ThemeGallery()

    def test_empty(self):
        self.assertEqual(self.g.count, 0)
        self.assertEqual(self.g.active_theme, "")

    def test_add_and_get(self):
        self.g.add(_theme("x"))
        self.assertEqual(self.g.count, 1)
        self.assertIsNotNone(self.g.get("x"))

    def test_add_requires_name(self):
        with self.assertRaises(ValueError):
            self.g.add(Theme(name="", author="a"))

    def test_remove(self):
        self.g.add(_theme("x"))
        self.assertTrue(self.g.remove("x"))
        self.assertFalse(self.g.remove("x"))

    def test_remove_active_resets(self):
        self.g.add(_theme("x"))
        self.g.install_theme("x")
        self.assertEqual(self.g.active_theme, "x")
        self.g.remove("x")
        self.assertEqual(self.g.active_theme, "")

    def test_install_theme(self):
        self.g.add(_theme("x"))
        self.assertTrue(self.g.install_theme("x"))
        self.assertEqual(self.g.active_theme, "x")
        self.assertEqual(self.g.get("x").installs, 1)

    def test_install_not_found(self):
        self.assertFalse(self.g.install_theme("nope"))

    def test_rate_theme(self):
        self.g.add(_theme("x"))
        self.assertTrue(self.g.rate_theme("x", 5))
        self.assertAlmostEqual(self.g.get("x").average_rating, 5.0)

    def test_rate_not_found(self):
        self.assertFalse(self.g.rate_theme("nope", 3))

    def test_browse(self):
        self.g.add(_theme("a"))
        self.g.add(_theme("b"))
        self.assertEqual(len(self.g.browse()), 2)

    def test_trending(self):
        self.g.add(_theme("a"))
        self.g.rate_theme("a", 4)
        self.g.add(_theme("b"))
        trending = self.g.trending()
        self.assertEqual(len(trending), 1)
        self.assertEqual(trending[0].name, "a")

    def test_top_rated(self):
        self.g.add(_theme("a"))
        self.g.rate_theme("a", 5)
        self.g.add(_theme("b"))
        self.g.rate_theme("b", 3)
        top = self.g.top_rated()
        self.assertEqual(top[0].name, "a")

    def test_seasonal(self):
        self.g.add(_theme("winter-glow", season=ThemeSeason.WINTER))
        self.g.add(_theme("summer-vibes", season=ThemeSeason.SUMMER))
        winter = self.g.seasonal(ThemeSeason.WINTER)
        self.assertEqual(len(winter), 1)
        self.assertEqual(winter[0].name, "winter-glow")

    def test_search(self):
        self.g.add(_theme("ocean-blue", description="Cool blue theme"))
        self.g.add(_theme("fire-red", description="Hot red theme"))
        results = self.g.search("blue")
        self.assertEqual(len(results), 1)

    def test_search_by_tag(self):
        self.g.add(_theme("x", tags=["minimal"]))
        results = self.g.search("minimal")
        self.assertEqual(len(results), 1)

    def test_preview(self):
        self.g.add(_theme("x"))
        pv = self.g.preview("x")
        self.assertIsNotNone(pv)
        self.assertEqual(pv["name"], "x")

    def test_preview_not_found(self):
        self.assertIsNone(self.g.preview("nope"))

    def test_stats(self):
        self.g.add(_theme("a"))
        st = self.g.stats()
        self.assertEqual(st["total_themes"], 1)


if __name__ == "__main__":
    unittest.main()
