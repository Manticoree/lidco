"""Tests for the configuration system."""

import pytest
from pathlib import Path

from lidco.core.config import (
    LidcoConfig,
    LLMConfig,
    PermissionsConfig,
    PermissionLevel,
    load_yaml_config,
    _deep_merge,
    load_config,
)


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"llm": {"model": "gpt-4", "temp": 0.5}}
        override = {"llm": {"temp": 0.1}}
        result = _deep_merge(base, override)
        assert result == {"llm": {"model": "gpt-4", "temp": 0.1}}

    def test_empty_override(self):
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == {"a": 1}

    def test_empty_base(self):
        result = _deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_does_not_mutate_base(self):
        base = {"a": {"x": 1}}
        _deep_merge(base, {"a": {"y": 2}})
        assert base == {"a": {"x": 1}}


class TestLidcoConfig:
    def test_defaults(self):
        config = LidcoConfig()
        assert config.llm.default_model == "gpt-4o-mini"
        assert config.llm.temperature == 0.1
        assert config.llm.streaming is True
        assert config.agents.default == "coder"
        assert config.memory.enabled is True

    def test_custom_values(self):
        config = LidcoConfig(
            llm=LLMConfig(default_model="claude-sonnet-4-5-20250514", temperature=0.5)
        )
        assert config.llm.default_model == "claude-sonnet-4-5-20250514"
        assert config.llm.temperature == 0.5


class TestPermissionsConfig:
    def test_auto_allow(self):
        config = PermissionsConfig()
        assert config.get_level("file_read") == PermissionLevel.AUTO

    def test_ask_level(self):
        config = PermissionsConfig()
        assert config.get_level("bash") == PermissionLevel.ASK

    def test_deny_level(self):
        config = PermissionsConfig(deny=["dangerous_tool"])
        assert config.get_level("dangerous_tool") == PermissionLevel.DENY

    def test_unknown_defaults_to_ask(self):
        config = PermissionsConfig()
        assert config.get_level("unknown_tool") == PermissionLevel.ASK


class TestLoadYamlConfig:
    def test_nonexistent_file(self, tmp_path):
        result = load_yaml_config(tmp_path / "nope.yaml")
        assert result == {}

    def test_valid_yaml(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("llm:\n  default_model: test-model\n")
        result = load_yaml_config(yaml_file)
        assert result == {"llm": {"default_model": "test-model"}}

    def test_empty_yaml(self, tmp_path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        result = load_yaml_config(yaml_file)
        assert result == {}


class TestLoadConfig:
    def test_loads_defaults(self):
        config = load_config()
        assert isinstance(config, LidcoConfig)
        assert config.llm.default_model is not None
