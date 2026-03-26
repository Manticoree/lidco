"""Tests for T619 ConfigManager."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from lidco.core.config_manager import ConfigManager, _deep_merge, _coerce, _get_nested, _set_nested


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_simple_override(self):
        result = _deep_merge({"a": 1, "b": 2}, {"b": 3, "c": 4})
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"llm": {"model": "gpt-4", "temp": 0.7}}
        override = {"llm": {"model": "claude-3"}}
        result = _deep_merge(base, override)
        assert result["llm"]["model"] == "claude-3"
        assert result["llm"]["temp"] == 0.7

    def test_does_not_mutate(self):
        base = {"x": {"y": 1}}
        override = {"x": {"z": 2}}
        result = _deep_merge(base, override)
        assert "z" not in base["x"]
        assert result["x"] == {"y": 1, "z": 2}


class TestCoerce:
    def test_true_values(self):
        for v in ("true", "True", "yes", "1", "on"):
            assert _coerce(v) is True

    def test_false_values(self):
        for v in ("false", "False", "no", "0", "off"):
            assert _coerce(v) is False

    def test_integer(self):
        assert _coerce("42") == 42

    def test_float(self):
        assert abs(_coerce("3.14") - 3.14) < 0.001

    def test_string_passthrough(self):
        assert _coerce("hello") == "hello"

    def test_type_hint(self):
        assert _coerce("42", int) == 42
        assert _coerce("hello", str) == "hello"


class TestGetSetNested:
    def test_get_flat(self):
        assert _get_nested({"a": 1}, ["a"]) == 1

    def test_get_nested(self):
        assert _get_nested({"a": {"b": 2}}, ["a", "b"]) == 2

    def test_get_missing_raises(self):
        with pytest.raises(KeyError):
            _get_nested({}, ["x"])

    def test_set_flat(self):
        result = _set_nested({}, ["a"], 1)
        assert result == {"a": 1}

    def test_set_nested(self):
        result = _set_nested({}, ["a", "b", "c"], 42)
        assert result["a"]["b"]["c"] == 42

    def test_set_does_not_mutate(self):
        orig = {"a": 1}
        _set_nested(orig, ["b"], 2)
        assert "b" not in orig


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class TestConfigManagerDefaults:
    def test_get_with_defaults(self):
        mgr = ConfigManager(defaults={"llm": {"model": "gpt-4"}})
        assert mgr.get("llm.model") == "gpt-4"

    def test_get_missing_returns_default(self):
        mgr = ConfigManager(defaults={})
        assert mgr.get("nonexistent", "fallback") == "fallback"

    def test_get_required_raises(self):
        mgr = ConfigManager()
        with pytest.raises(KeyError):
            mgr.get_required("missing.key")

    def test_getitem_success(self):
        mgr = ConfigManager(defaults={"key": "value"})
        assert mgr["key"] == "value"

    def test_getitem_missing_raises(self):
        mgr = ConfigManager()
        with pytest.raises(KeyError):
            _ = mgr["nonexistent"]

    def test_all_returns_copy(self):
        mgr = ConfigManager(defaults={"x": 1})
        d = mgr.all()
        d["x"] = 999
        assert mgr.get("x") == 1  # Not mutated


class TestConfigManagerSet:
    def test_set_flat(self):
        mgr = ConfigManager()
        mgr.set("debug", True)
        assert mgr.get("debug") is True

    def test_set_nested(self):
        mgr = ConfigManager()
        mgr.set("llm.model", "claude-3")
        assert mgr.get("llm.model") == "claude-3"

    def test_set_overrides_defaults(self):
        mgr = ConfigManager(defaults={"llm": {"model": "gpt-4"}})
        mgr.set("llm.model", "claude-3")
        assert mgr.get("llm.model") == "claude-3"

    def test_set_preserves_siblings(self):
        mgr = ConfigManager(defaults={"llm": {"model": "gpt-4", "temp": 0.7}})
        mgr.set("llm.model", "claude-3")
        assert mgr.get("llm.temp") == 0.7


class TestConfigManagerProjectFile:
    def test_loads_project_json(self, tmp_path):
        config_dir = tmp_path / ".lidco"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({"api_key": "test123"}))
        mgr = ConfigManager(project_root=str(tmp_path))
        assert mgr.get("api_key") == "test123"

    def test_project_overrides_defaults(self, tmp_path):
        config_dir = tmp_path / ".lidco"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({"model": "project_model"}))
        mgr = ConfigManager(
            defaults={"model": "default_model"},
            project_root=str(tmp_path),
        )
        assert mgr.get("model") == "project_model"

    def test_save_creates_file(self, tmp_path):
        mgr = ConfigManager(project_root=str(tmp_path))
        mgr.set("new_key", "new_value")
        saved_path = mgr.save()
        assert saved_path.exists()
        data = json.loads(saved_path.read_text())
        assert data.get("new_key") == "new_value"

    def test_save_merges_with_existing(self, tmp_path):
        config_dir = tmp_path / ".lidco"
        config_dir.mkdir()
        existing = config_dir / "config.json"
        existing.write_text(json.dumps({"keep": "this"}))
        mgr = ConfigManager(project_root=str(tmp_path))
        mgr.set("new", "val")
        mgr.save()
        data = json.loads(existing.read_text())
        assert data.get("keep") == "this"
        assert data.get("new") == "val"

    def test_reload(self, tmp_path):
        config_dir = tmp_path / ".lidco"
        config_dir.mkdir()
        cfg_file = config_dir / "config.json"
        cfg_file.write_text(json.dumps({"dynamic": "v1"}))
        mgr = ConfigManager(project_root=str(tmp_path))
        assert mgr.get("dynamic") == "v1"
        cfg_file.write_text(json.dumps({"dynamic": "v2"}))
        mgr.reload()
        assert mgr.get("dynamic") == "v2"


class TestConfigManagerEnvVars:
    def test_env_var_override(self, tmp_path):
        with patch.dict(os.environ, {"LIDCO_DEBUG": "true"}):
            mgr = ConfigManager(project_root=str(tmp_path))
        assert mgr.get("debug") is True

    def test_env_var_nested(self, tmp_path):
        with patch.dict(os.environ, {"LIDCO_LLM_MODEL": "env-model"}):
            mgr = ConfigManager(project_root=str(tmp_path))
        assert mgr.get("llm.model") == "env-model"

    def test_custom_prefix(self, tmp_path):
        with patch.dict(os.environ, {"MYAPP_KEY": "myvalue"}):
            mgr = ConfigManager(project_root=str(tmp_path), env_prefix="MYAPP")
        assert mgr.get("key") == "myvalue"

    def test_env_higher_priority_than_project(self, tmp_path):
        config_dir = tmp_path / ".lidco"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps({"model": "project_val"}))
        with patch.dict(os.environ, {"LIDCO_MODEL": "env_val"}):
            mgr = ConfigManager(project_root=str(tmp_path))
        assert mgr.get("model") == "env_val"
