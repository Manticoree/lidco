"""Tests for src/lidco/themes/icons.py."""
from __future__ import annotations

from lidco.themes.icons import Icon, IconSet


class TestIcon:
    def test_frozen(self):
        i = Icon(name="x", unicode="✓", ascii_fallback="[OK]")
        try:
            i.name = "y"  # type: ignore[misc]
            assert False, "Should have raised"
        except AttributeError:
            pass

    def test_defaults(self):
        i = Icon(name="x", unicode="✓", ascii_fallback="[OK]")
        assert i.category == "general"


class TestIconSet:
    def test_default_icons_present(self):
        s = IconSet()
        assert s.get("success") == "✓"
        assert s.get("error") == "✗"

    def test_unicode_mode(self):
        s = IconSet(use_unicode=True)
        assert s.get("success") == "✓"

    def test_ascii_mode(self):
        s = IconSet(use_unicode=False)
        assert s.get("success") == "[OK]"
        assert s.get("error") == "[ERR]"

    def test_toggle_unicode(self):
        s = IconSet(use_unicode=True)
        s.toggle_unicode(False)
        assert s.get("success") == "[OK]"
        s.toggle_unicode(True)
        assert s.get("success") == "✓"

    def test_set_custom_icon(self):
        s = IconSet()
        s.set("rocket", "🚀", "[ROCKET]", category="custom")
        assert s.get("rocket") == "🚀"

    def test_remove_icon(self):
        s = IconSet()
        assert s.remove("success") is True
        assert s.get("success") == ""

    def test_remove_nonexistent(self):
        s = IconSet()
        assert s.remove("nope") is False

    def test_by_category(self):
        s = IconSet()
        status = s.by_category("status")
        names = [i.name for i in status]
        assert "success" in names
        assert "error" in names

    def test_all_icons(self):
        s = IconSet()
        assert len(s.all_icons()) == 8

    def test_summary(self):
        s = IconSet()
        sm = s.summary()
        assert sm["total"] == 8
        assert sm["use_unicode"] is True
        assert "status" in sm["categories"]
