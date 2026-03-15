"""Tests for KeybindingLoader and DEFAULT_BINDINGS — Q64 Task 432."""

from __future__ import annotations

import json
import pytest
from pathlib import Path


class TestDefaultBindings:
    def test_submit_action_defined(self):
        from lidco.cli.keybindings import DEFAULT_BINDINGS
        assert "submit" in DEFAULT_BINDINGS

    def test_clear_action_defined(self):
        from lidco.cli.keybindings import DEFAULT_BINDINGS
        assert "clear" in DEFAULT_BINDINGS

    def test_abort_action_defined(self):
        from lidco.cli.keybindings import DEFAULT_BINDINGS
        assert "abort" in DEFAULT_BINDINGS

    def test_all_values_are_strings(self):
        from lidco.cli.keybindings import DEFAULT_BINDINGS
        for k, v in DEFAULT_BINDINGS.items():
            assert isinstance(v, str)


class TestKeybindingConfig:
    def test_get_returns_binding(self):
        from lidco.cli.keybindings import KeybindingConfig
        cfg = KeybindingConfig()
        assert cfg.get("submit") == "enter"

    def test_get_returns_none_for_unknown(self):
        from lidco.cli.keybindings import KeybindingConfig
        cfg = KeybindingConfig()
        assert cfg.get("nonexistent_action") is None

    def test_set_returns_new_config(self):
        from lidco.cli.keybindings import KeybindingConfig
        cfg = KeybindingConfig()
        new_cfg = cfg.set("submit", "ctrl+enter")
        assert new_cfg.get("submit") == "ctrl+enter"
        assert cfg.get("submit") == "enter"  # immutable

    def test_reset_returns_defaults(self):
        from lidco.cli.keybindings import KeybindingConfig, DEFAULT_BINDINGS
        cfg = KeybindingConfig(bindings={"submit": "ctrl+enter"})
        reset = cfg.reset()
        assert reset.get("submit") == DEFAULT_BINDINGS["submit"]

    def test_list_actions_sorted(self):
        from lidco.cli.keybindings import KeybindingConfig
        cfg = KeybindingConfig()
        actions = cfg.list_actions()
        assert actions == sorted(actions)


class TestKeybindingLoader:
    def test_load_defaults_when_no_file(self, tmp_path):
        from lidco.cli.keybindings import KeybindingLoader, DEFAULT_BINDINGS
        loader = KeybindingLoader(path=tmp_path / "keybindings.json")
        cfg = loader.load()
        assert cfg.get("submit") == DEFAULT_BINDINGS["submit"]

    def test_load_merges_user_overrides(self, tmp_path):
        from lidco.cli.keybindings import KeybindingLoader
        kb_file = tmp_path / "keybindings.json"
        kb_file.write_text(json.dumps({"submit": "ctrl+enter"}))
        loader = KeybindingLoader(path=kb_file)
        cfg = loader.load()
        assert cfg.get("submit") == "ctrl+enter"

    def test_save_only_writes_overrides(self, tmp_path):
        from lidco.cli.keybindings import KeybindingLoader, KeybindingConfig, DEFAULT_BINDINGS
        kb_file = tmp_path / "keybindings.json"
        loader = KeybindingLoader(path=kb_file)
        cfg = KeybindingConfig(bindings={**DEFAULT_BINDINGS, "submit": "ctrl+enter"})
        loader.save(cfg)
        data = json.loads(kb_file.read_text())
        assert "submit" in data
        # Default values should not appear
        assert "abort" not in data

    def test_load_handles_invalid_json(self, tmp_path):
        from lidco.cli.keybindings import KeybindingLoader, DEFAULT_BINDINGS
        kb_file = tmp_path / "keybindings.json"
        kb_file.write_text("{ invalid json }")
        loader = KeybindingLoader(path=kb_file)
        cfg = loader.load()
        # Falls back to defaults
        assert cfg.get("submit") == DEFAULT_BINDINGS["submit"]

    def test_load_preserves_unknown_custom_actions(self, tmp_path):
        from lidco.cli.keybindings import KeybindingLoader
        kb_file = tmp_path / "keybindings.json"
        kb_file.write_text(json.dumps({"my_custom_action": "ctrl+alt+x"}))
        loader = KeybindingLoader(path=kb_file)
        cfg = loader.load()
        assert cfg.get("my_custom_action") == "ctrl+alt+x"
