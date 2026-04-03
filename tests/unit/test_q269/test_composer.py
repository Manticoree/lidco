"""Tests for src/lidco/themes/composer.py."""
from __future__ import annotations

import json

import pytest

from lidco.themes.composer import ThemeComposer
from lidco.themes.registry import Theme, ThemeRegistry


class TestThemeComposer:
    def _make(self):
        reg = ThemeRegistry()
        return ThemeComposer(reg), reg

    def test_extend_creates_new_theme(self):
        comp, reg = self._make()
        t = comp.extend("dark", {"colors": {"bg": "#000"}}, "my-dark")
        assert t.name == "my-dark"
        assert t.colors["bg"] == "#000"
        # Other colors inherited from dark
        assert "fg" in t.colors

    def test_extend_unknown_base_raises(self):
        comp, _ = self._make()
        with pytest.raises(ValueError, match="not found"):
            comp.extend("nope", {}, "x")

    def test_merge_b_overrides_a(self):
        comp, reg = self._make()
        t = comp.merge("dark", "light", "merged")
        # light bg should win
        assert t.colors["bg"] == "#ffffff"

    def test_merge_unknown_raises(self):
        comp, _ = self._make()
        with pytest.raises(ValueError):
            comp.merge("dark", "nope", "x")

    def test_export_import_roundtrip(self):
        comp, reg = self._make()
        json_str = comp.export_theme("dark")
        data = json.loads(json_str)
        assert data["name"] == "dark"
        # Import under a new name
        data["name"] = "dark-copy"
        imported = comp.import_theme(json.dumps(data))
        assert imported.name == "dark-copy"
        assert reg.get("dark-copy") is not None

    def test_export_unknown_raises(self):
        comp, _ = self._make()
        with pytest.raises(ValueError, match="not found"):
            comp.export_theme("nope")

    def test_import_invalid_json_raises(self):
        comp, _ = self._make()
        with pytest.raises(json.JSONDecodeError):
            comp.import_theme("{bad json")

    def test_preview_has_theme_name(self):
        comp, _ = self._make()
        preview = comp.preview("dark")
        assert "dark" in preview
        assert "Colors:" in preview

    def test_preview_unknown_raises(self):
        comp, _ = self._make()
        with pytest.raises(ValueError):
            comp.preview("nope")

    def test_summary(self):
        comp, _ = self._make()
        s = comp.summary()
        assert s["registry_themes"] == 5
