"""Tests for src/lidco/themes/palette.py."""
from __future__ import annotations

from lidco.themes.palette import Color, ColorPalette


class TestColor:
    def test_frozen(self):
        c = Color(name="red", hex="#ff0000")
        try:
            c.name = "blue"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass

    def test_defaults(self):
        c = Color(name="x", hex="#000")
        assert c.ansi256 == 0
        assert c.semantic == ""


class TestColorPalette:
    def test_defaults_have_semantic_colors(self):
        p = ColorPalette()
        assert p.get_semantic("error") is not None
        assert p.get_semantic("success") is not None

    def test_set_and_get(self):
        p = ColorPalette()
        p.set("coral", "#ff7f50", ansi256=209)
        c = p.get("coral")
        assert c is not None
        assert c.hex == "#ff7f50"

    def test_get_nonexistent(self):
        p = ColorPalette()
        assert p.get("nope") is None

    def test_get_semantic_missing(self):
        p = ColorPalette()
        assert p.get_semantic("nonexistent") is None

    def test_remove(self):
        p = ColorPalette()
        p.set("tmp", "#000")
        assert p.remove("tmp") is True
        assert p.get("tmp") is None

    def test_remove_nonexistent(self):
        p = ColorPalette()
        assert p.remove("nope") is False

    def test_all_colors(self):
        p = ColorPalette()
        assert len(p.all_colors()) == 6  # default semantics

    def test_by_semantic(self):
        p = ColorPalette()
        sem = p.by_semantic()
        assert "error" in sem
        assert "warning" in sem

    def test_to_dict_and_from_dict(self):
        p = ColorPalette()
        d = p.to_dict()
        p2 = ColorPalette()
        p2.from_dict({})  # no-op
        p2.from_dict(d)
        assert p2.get("red") is not None
        assert p2.get("red").hex == "#ff0000"

    def test_summary(self):
        p = ColorPalette()
        s = p.summary()
        assert s["total"] == 6
        assert "error" in s["semantic_tokens"]
