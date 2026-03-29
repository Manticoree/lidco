"""Tests for SessionColorManager — Task 730."""

from __future__ import annotations

import json
import unittest

from lidco.config.session_color import (
    ColorError,
    NAMED_COLORS,
    SessionColorManager,
)


class TestNamedColors(unittest.TestCase):
    """NAMED_COLORS dict validation."""

    def test_has_basic_colors(self):
        for name in ("red", "green", "blue", "yellow", "cyan", "magenta", "white"):
            self.assertIn(name, NAMED_COLORS)

    def test_has_bright_colors(self):
        for name in ("bright_red", "bright_green", "bright_blue"):
            self.assertIn(name, NAMED_COLORS)

    def test_has_default_and_reset(self):
        self.assertIn("default", NAMED_COLORS)
        self.assertIn("reset", NAMED_COLORS)

    def test_values_are_ansi_escapes(self):
        for v in NAMED_COLORS.values():
            self.assertTrue(v.startswith("\033["), f"Expected ANSI escape, got {v!r}")


class TestSessionColorManager(unittest.TestCase):
    """Core functionality."""

    def _manager(self, stored=None):
        written = {}

        def write_fn(path, data):
            written[path] = data

        def read_fn(path):
            if stored:
                return stored
            raise FileNotFoundError

        mgr = SessionColorManager(store_path="/tmp/color.json", write_fn=write_fn, read_fn=read_fn)
        mgr._written = written
        return mgr

    def test_initial_color_is_none(self):
        mgr = self._manager()
        self.assertIsNone(mgr.get_color())

    def test_set_named_color(self):
        mgr = self._manager()
        result = mgr.set_color("red")
        self.assertEqual(result, "red")
        self.assertEqual(mgr.get_color(), "red")

    def test_set_hex_color(self):
        mgr = self._manager()
        result = mgr.set_color("#FF0000")
        self.assertEqual(result, "#FF0000")
        self.assertEqual(mgr.get_color(), "#FF0000")

    def test_set_hex_lowercase(self):
        mgr = self._manager()
        result = mgr.set_color("#aabbcc")
        self.assertEqual(result, "#aabbcc")

    def test_invalid_name_raises(self):
        mgr = self._manager()
        with self.assertRaises(ColorError):
            mgr.set_color("chartreuse")

    def test_invalid_hex_short(self):
        mgr = self._manager()
        with self.assertRaises(ColorError):
            mgr.set_color("#FFF")

    def test_invalid_hex_no_hash(self):
        mgr = self._manager()
        with self.assertRaises(ColorError):
            mgr.set_color("FF0000")

    def test_invalid_hex_bad_chars(self):
        mgr = self._manager()
        with self.assertRaises(ColorError):
            mgr.set_color("#GGGGGG")

    def test_set_color_persists(self):
        mgr = self._manager()
        mgr.set_color("blue")
        self.assertIn("/tmp/color.json", mgr._written)

    def test_get_ansi_prefix_named(self):
        mgr = self._manager()
        mgr.set_color("green")
        prefix = mgr.get_ansi_prefix()
        self.assertEqual(prefix, NAMED_COLORS["green"])

    def test_get_ansi_prefix_hex_returns_empty(self):
        mgr = self._manager()
        mgr.set_color("#112233")
        prefix = mgr.get_ansi_prefix()
        self.assertEqual(prefix, "")

    def test_get_ansi_prefix_no_color_returns_empty(self):
        mgr = self._manager()
        prefix = mgr.get_ansi_prefix()
        self.assertEqual(prefix, "")

    def test_reset(self):
        mgr = self._manager()
        mgr.set_color("red")
        mgr.reset()
        self.assertIsNone(mgr.get_color())
        self.assertEqual(mgr.get_ansi_prefix(), "")

    def test_list_colors_sorted(self):
        mgr = self._manager()
        colors = mgr.list_colors()
        self.assertEqual(colors, sorted(colors))
        self.assertIn("red", colors)
        self.assertIn("blue", colors)

    def test_list_colors_returns_list(self):
        mgr = self._manager()
        self.assertIsInstance(mgr.list_colors(), list)

    def test_set_all_named_colors(self):
        mgr = self._manager()
        for name in NAMED_COLORS:
            result = mgr.set_color(name)
            self.assertEqual(result, name)

    def test_persist_format(self):
        mgr = self._manager()
        mgr.set_color("cyan")
        data = json.loads(mgr._written["/tmp/color.json"])
        self.assertEqual(data["color"], "cyan")

    def test_hex_uppercase_valid(self):
        mgr = self._manager()
        result = mgr.set_color("#AABB00")
        self.assertEqual(result, "#AABB00")

    def test_empty_string_raises(self):
        mgr = self._manager()
        with self.assertRaises(ColorError):
            mgr.set_color("")


if __name__ == "__main__":
    unittest.main()
