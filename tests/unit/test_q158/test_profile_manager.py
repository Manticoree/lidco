"""Tests for Task 903 — ProfileManager stores LidcoConfig snapshots."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lidco.config.profile import ConfigProfile, ProfileManager
from lidco.core.config import LidcoConfig


class TestProfileManagerApplyTo:
    """ProfileManager.apply_to merges profile into LidcoConfig."""

    def _make_manager(self) -> ProfileManager:
        buf: dict[str, str] = {}
        def write_fn(path, data):
            buf[path] = data
        def read_fn(path):
            return buf.get(path, "[]")
        return ProfileManager(store_path="/fake/profiles.json", write_fn=write_fn, read_fn=read_fn)

    def test_apply_to_merges_settings(self):
        mgr = self._make_manager()
        mgr.create("fast", settings={"llm": {"temperature": 0.0, "max_tokens": 256}})
        cfg = LidcoConfig()
        result = mgr.apply_to("fast", cfg)
        assert result.llm.temperature == 0.0
        assert result.llm.max_tokens == 256
        # Original not mutated
        assert cfg.llm.temperature != 0.0 or cfg.llm.max_tokens != 256

    def test_apply_to_returns_new_instance(self):
        mgr = self._make_manager()
        mgr.create("test", settings={"llm": {"streaming": False}})
        cfg = LidcoConfig()
        result = mgr.apply_to("test", cfg)
        assert result is not cfg
        assert result.llm.streaming is False
        assert cfg.llm.streaming is True

    def test_apply_to_missing_profile_raises(self):
        mgr = self._make_manager()
        cfg = LidcoConfig()
        with pytest.raises(KeyError, match="no-such"):
            mgr.apply_to("no-such", cfg)

    def test_apply_to_partial_settings(self):
        mgr = self._make_manager()
        mgr.create("partial", settings={"agents": {"max_iterations": 50}})
        cfg = LidcoConfig()
        result = mgr.apply_to("partial", cfg)
        assert result.agents.max_iterations == 50
        # Other fields untouched
        assert result.llm.default_model == cfg.llm.default_model


class TestProfileManagerCreateFromConfig:
    """ProfileManager.create snapshots LidcoConfig."""

    def _make_manager(self) -> ProfileManager:
        buf: dict[str, str] = {}
        def write_fn(path, data):
            buf[path] = data
        def read_fn(path):
            return buf.get(path, "[]")
        return ProfileManager(store_path="/fake/profiles.json", write_fn=write_fn, read_fn=read_fn)

    def test_create_from_config(self):
        mgr = self._make_manager()
        cfg = LidcoConfig()
        cfg.llm.temperature = 0.42
        profile = mgr.create("snapshot", config=cfg)
        assert profile.settings["llm"]["temperature"] == 0.42

    def test_create_from_config_has_all_sections(self):
        mgr = self._make_manager()
        cfg = LidcoConfig()
        profile = mgr.create("full", config=cfg)
        assert "llm" in profile.settings
        assert "agents" in profile.settings
        assert "memory" in profile.settings

    def test_create_config_overrides_settings_param(self):
        mgr = self._make_manager()
        cfg = LidcoConfig()
        profile = mgr.create("x", settings={"should": "be_ignored"}, config=cfg)
        # config snapshot wins
        assert "llm" in profile.settings
        assert "should" not in profile.settings

    def test_create_without_config_uses_settings(self):
        mgr = self._make_manager()
        profile = mgr.create("plain", settings={"key": "val"})
        assert profile.settings == {"key": "val"}

    def test_create_without_config_or_settings(self):
        mgr = self._make_manager()
        profile = mgr.create("empty")
        assert profile.settings == {}


class TestProfileManagerBackwardCompat:
    """Existing API still works unchanged."""

    def _make_manager(self) -> ProfileManager:
        buf: dict[str, str] = {}
        def write_fn(path, data):
            buf[path] = data
        def read_fn(path):
            return buf.get(path, "[]")
        return ProfileManager(store_path="/fake/profiles.json", write_fn=write_fn, read_fn=read_fn)

    def test_create_with_dict_settings(self):
        mgr = self._make_manager()
        p = mgr.create("dev", {"debug": True})
        assert p.settings == {"debug": True}

    def test_list_and_delete(self):
        mgr = self._make_manager()
        mgr.create("a", {"x": 1})
        mgr.create("b", {"y": 2})
        assert len(mgr.list_all()) == 2
        mgr.delete("a")
        assert len(mgr.list_all()) == 1

    def test_activate(self):
        mgr = self._make_manager()
        mgr.create("dev", {"x": 1})
        mgr.activate("dev")
        assert mgr.active().name == "dev"
