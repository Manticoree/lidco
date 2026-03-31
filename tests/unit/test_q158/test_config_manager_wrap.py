"""Tests for Task 902 — ConfigManager wraps LidcoConfig."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lidco.core.config import LidcoConfig
from lidco.core.config_manager import ConfigManager


class TestConfigManagerWithLidcoConfig:
    """ConfigManager delegates to LidcoConfig when attached."""

    def test_constructor_accepts_config(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        assert mgr._lidco_config is cfg

    def test_constructor_without_config_still_works(self):
        mgr = ConfigManager(defaults={"foo": "bar"})
        assert mgr._lidco_config is None
        assert mgr.get("foo") == "bar"

    def test_get_resolves_dot_notation_on_model(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        assert mgr.get("llm.default_model") == cfg.llm.default_model

    def test_get_resolves_nested_model_attr(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        assert mgr.get("llm.temperature") == cfg.llm.temperature

    def test_get_falls_back_to_default_for_missing(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        assert mgr.get("nonexistent.key", "fallback") == "fallback"

    def test_set_updates_model_attribute(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        mgr.set("llm.temperature", 0.99)
        assert cfg.llm.temperature == 0.99
        assert mgr.get("llm.temperature") == 0.99

    def test_set_unknown_key_still_in_runtime(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        mgr.set("custom.key", "val")
        assert mgr.get("custom.key") == "val"

    def test_all_serialises_model(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        result = mgr.all()
        assert isinstance(result, dict)
        assert "llm" in result
        assert result["llm"]["default_model"] == cfg.llm.default_model

    def test_all_includes_runtime_overrides(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        mgr.set("extra_key", "extra_val")
        result = mgr.all()
        assert result["extra_key"] == "extra_val"

    def test_reload_seeds_from_model(self):
        cfg = LidcoConfig()
        cfg.llm.temperature = 0.77
        mgr = ConfigManager(config=cfg)
        mgr.reload()
        # After reload, merged config should contain model values
        assert mgr.get("llm.temperature") == 0.77

    def test_backward_compat_no_config(self):
        """Without a LidcoConfig, original JSON/TOML loading path works."""
        with tempfile.TemporaryDirectory() as td:
            lidco_dir = Path(td) / ".lidco"
            lidco_dir.mkdir()
            cfg_file = lidco_dir / "config.json"
            cfg_file.write_text(json.dumps({"llm": {"model": "test-model"}}))
            mgr = ConfigManager(project_root=td)
            assert mgr.get("llm.model") == "test-model"

    def test_get_required_with_model(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        assert mgr.get_required("llm.streaming") is True

    def test_getitem_with_model(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        assert mgr["llm.streaming"] is True

    def test_getitem_missing_raises(self):
        cfg = LidcoConfig()
        mgr = ConfigManager(config=cfg)
        with pytest.raises(KeyError):
            _ = mgr["totally.missing.key"]


class TestConfigManagerBackwardCompat:
    """Ensure no regressions in the original (no LidcoConfig) path."""

    def test_defaults_only(self):
        mgr = ConfigManager(defaults={"a": {"b": 1}})
        assert mgr.get("a.b") == 1

    def test_set_and_get(self):
        mgr = ConfigManager()
        mgr.set("x.y", 42)
        assert mgr.get("x.y") == 42

    def test_all_returns_copy(self):
        mgr = ConfigManager(defaults={"k": "v"})
        d = mgr.all()
        d["k"] = "changed"
        assert mgr.get("k") == "v"
