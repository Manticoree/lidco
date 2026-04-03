"""Tests for src/lidco/themes/registry.py."""
from __future__ import annotations

from lidco.themes.registry import Theme, ThemeRegistry


class TestTheme:
    def test_theme_defaults(self):
        t = Theme(name="test")
        assert t.name == "test"
        assert t.colors == {}
        assert t.icons == {}
        assert t.description == ""
        assert t.author == "system"

    def test_theme_with_colors(self):
        t = Theme(name="x", colors={"bg": "#000"}, description="desc")
        assert t.colors["bg"] == "#000"
        assert t.description == "desc"


class TestThemeRegistry:
    def test_builtin_themes_present(self):
        reg = ThemeRegistry()
        names = reg.builtin_names()
        assert "dark" in names
        assert "light" in names
        assert "monokai" in names
        assert "solarized" in names
        assert "dracula" in names

    def test_default_active_is_dark(self):
        reg = ThemeRegistry()
        assert reg.active().name == "dark"

    def test_set_active(self):
        reg = ThemeRegistry()
        assert reg.set_active("light") is True
        assert reg.active().name == "light"

    def test_set_active_unknown(self):
        reg = ThemeRegistry()
        assert reg.set_active("nonexistent") is False
        assert reg.active().name == "dark"

    def test_register_custom_theme(self):
        reg = ThemeRegistry()
        t = Theme(name="custom", colors={"bg": "#111"}, author="user")
        reg.register(t)
        assert reg.get("custom") is t

    def test_get_nonexistent(self):
        reg = ThemeRegistry()
        assert reg.get("nope") is None

    def test_remove_custom(self):
        reg = ThemeRegistry()
        reg.register(Theme(name="tmp"))
        assert reg.remove("tmp") is True
        assert reg.get("tmp") is None

    def test_cannot_remove_builtin(self):
        reg = ThemeRegistry()
        assert reg.remove("dark") is False
        assert reg.get("dark") is not None

    def test_remove_nonexistent(self):
        reg = ThemeRegistry()
        assert reg.remove("nope") is False

    def test_remove_active_resets_to_dark(self):
        reg = ThemeRegistry()
        reg.register(Theme(name="tmp"))
        reg.set_active("tmp")
        reg.remove("tmp")
        assert reg.active().name == "dark"

    def test_all_themes(self):
        reg = ThemeRegistry()
        assert len(reg.all_themes()) == 5

    def test_summary(self):
        reg = ThemeRegistry()
        s = reg.summary()
        assert s["total"] == 5
        assert s["builtin"] == 5
        assert s["custom"] == 0
        assert s["active"] == "dark"
        assert "dark" in s["names"]
