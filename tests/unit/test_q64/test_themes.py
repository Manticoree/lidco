"""Tests for ThemeManager and BUILT_IN_THEMES — Q64 Task 433."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock


class TestBuiltInThemes:
    def test_dark_theme_exists(self):
        from lidco.cli.theme import BUILT_IN_THEMES
        assert "dark" in BUILT_IN_THEMES

    def test_light_theme_exists(self):
        from lidco.cli.theme import BUILT_IN_THEMES
        assert "light" in BUILT_IN_THEMES

    def test_monokai_exists(self):
        from lidco.cli.theme import BUILT_IN_THEMES
        assert "monokai" in BUILT_IN_THEMES

    def test_dracula_exists(self):
        from lidco.cli.theme import BUILT_IN_THEMES
        assert "dracula" in BUILT_IN_THEMES

    def test_theme_has_required_fields(self):
        from lidco.cli.theme import BUILT_IN_THEMES, Theme
        for name, theme in BUILT_IN_THEMES.items():
            assert isinstance(theme, Theme)
            assert theme.name == name
            assert theme.primary
            assert theme.error


class TestThemeManager:
    def test_list_themes_contains_dark(self):
        from lidco.cli.theme import ThemeManager
        mgr = ThemeManager()
        assert "dark" in mgr.list_themes()

    def test_list_themes_sorted(self):
        from lidco.cli.theme import ThemeManager
        mgr = ThemeManager()
        themes = mgr.list_themes()
        assert themes == sorted(themes)

    def test_load_built_in(self):
        from lidco.cli.theme import ThemeManager
        mgr = ThemeManager()
        theme = mgr.load("dark")
        assert theme.name == "dark"

    def test_load_unknown_raises_key_error(self):
        from lidco.cli.theme import ThemeManager
        mgr = ThemeManager()
        with pytest.raises(KeyError):
            mgr.load("nonexistent_theme_xyz")

    def test_register_custom_theme(self):
        from lidco.cli.theme import ThemeManager, Theme
        mgr = ThemeManager()
        custom = Theme(
            name="my-theme",
            primary="purple",
            secondary="pink",
            accent="orange",
            background="black",
            error="red",
            warning="yellow",
            success="green",
        )
        mgr.register(custom)
        assert "my-theme" in mgr.list_themes()
        loaded = mgr.load("my-theme")
        assert loaded.primary == "purple"

    def test_apply_to_console(self):
        from lidco.cli.theme import ThemeManager
        mgr = ThemeManager()
        theme = mgr.load("dark")
        console = MagicMock()
        console.style = ""
        mgr.apply(theme, console)
        # Should not raise

    def test_load_custom_from_yaml(self, tmp_path):
        from lidco.cli.theme import ThemeManager, Theme
        # Write a YAML-like file (simple format)
        yaml_content = (
            "name: my-custom\n"
            "primary: cyan\n"
            "secondary: blue\n"
            "accent: yellow\n"
            "background: black\n"
            "error: red\n"
            "warning: orange\n"
            "success: green\n"
        )
        yaml_file = tmp_path / "my-custom.yaml"
        yaml_file.write_text(yaml_content)
        mgr = ThemeManager()
        theme = mgr.load_custom(yaml_file)
        assert theme.name == "my-custom"
        assert theme.primary == "cyan"

    def test_load_custom_missing_fields_raises(self, tmp_path):
        from lidco.cli.theme import ThemeManager
        bad_yaml = "name: bad\nprimary: red\n"  # missing many fields
        f = tmp_path / "bad.yaml"
        f.write_text(bad_yaml)
        mgr = ThemeManager()
        with pytest.raises(ValueError, match="missing"):
            mgr.load_custom(f)
