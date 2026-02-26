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
    _coerce_env_value,
    _apply_env_overrides,
    load_config,
)


class TestDeepMerge:
    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"llm": {"model": "openai/glm-4.7", "temp": 0.5}}
        override = {"llm": {"temp": 0.1}}
        result = _deep_merge(base, override)
        assert result == {"llm": {"model": "openai/glm-4.7", "temp": 0.1}}

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
        assert config.llm.default_model == "openai/glm-4.7"
        assert config.llm.temperature == 0.1
        assert config.llm.streaming is True
        assert config.agents.default == "coder"
        assert config.memory.enabled is True

    def test_custom_values(self):
        config = LidcoConfig(
            llm=LLMConfig(default_model="openai/glm-4.7", temperature=0.5)
        )
        assert config.llm.default_model == "openai/glm-4.7"
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


class TestCoerceEnvValue:
    def test_true_variants(self):
        for v in ("true", "True", "TRUE", "1", "yes", "YES"):
            assert _coerce_env_value(v) is True

    def test_false_variants(self):
        for v in ("false", "False", "FALSE", "0", "no", "NO"):
            assert _coerce_env_value(v) is False

    def test_integer(self):
        assert _coerce_env_value("42") == 42
        assert isinstance(_coerce_env_value("42"), int)

    def test_float(self):
        assert _coerce_env_value("3.14") == pytest.approx(3.14)

    def test_string_passthrough(self):
        assert _coerce_env_value("openai/glm-4.7") == "openai/glm-4.7"
        assert _coerce_env_value("monokai") == "monokai"


class TestApplyEnvOverrides:
    def test_override_llm_default_model(self, monkeypatch):
        monkeypatch.setenv("LIDCO_LLM_DEFAULT_MODEL", "openai/glm-4.7")
        config = _apply_env_overrides(LidcoConfig())
        assert config.llm.default_model == "openai/glm-4.7"

    def test_override_llm_temperature(self, monkeypatch):
        monkeypatch.setenv("LIDCO_LLM_TEMPERATURE", "0.7")
        config = _apply_env_overrides(LidcoConfig())
        assert config.llm.temperature == pytest.approx(0.7)

    def test_override_agents_auto_review_false(self, monkeypatch):
        monkeypatch.setenv("LIDCO_AGENTS_AUTO_REVIEW", "false")
        config = _apply_env_overrides(LidcoConfig())
        assert config.agents.auto_review is False

    def test_override_rag_enabled(self, monkeypatch):
        monkeypatch.setenv("LIDCO_RAG_ENABLED", "true")
        config = _apply_env_overrides(LidcoConfig())
        assert config.rag.enabled is True

    def test_override_memory_max_entries(self, monkeypatch):
        monkeypatch.setenv("LIDCO_MEMORY_MAX_ENTRIES", "100")
        config = _apply_env_overrides(LidcoConfig())
        assert config.memory.max_entries == 100

    def test_override_cli_theme(self, monkeypatch):
        monkeypatch.setenv("LIDCO_CLI_THEME", "dracula")
        config = _apply_env_overrides(LidcoConfig())
        assert config.cli.theme == "dracula"

    def test_unknown_section_ignored(self, monkeypatch):
        monkeypatch.setenv("LIDCO_NONEXISTENT_FIELD", "value")
        config = _apply_env_overrides(LidcoConfig())
        assert isinstance(config, LidcoConfig)  # no crash

    def test_unknown_field_within_section_ignored(self, monkeypatch):
        monkeypatch.setenv("LIDCO_LLM_TOTALLY_FAKE_FIELD", "x")
        config = _apply_env_overrides(LidcoConfig())
        assert isinstance(config, LidcoConfig)

    def test_no_lidco_vars_returns_unchanged(self, monkeypatch):
        # Remove all LIDCO_ vars
        for key in list(__import__("os").environ):
            if key.startswith("LIDCO_"):
                monkeypatch.delenv(key, raising=False)
        original = LidcoConfig()
        result = _apply_env_overrides(original)
        assert result.llm.default_model == original.llm.default_model

    def test_multiple_sections_at_once(self, monkeypatch):
        monkeypatch.setenv("LIDCO_LLM_MAX_TOKENS", "8192")
        monkeypatch.setenv("LIDCO_AGENTS_MAX_ITERATIONS", "50")
        config = _apply_env_overrides(LidcoConfig())
        assert config.llm.max_tokens == 8192
        assert config.agents.max_iterations == 50
