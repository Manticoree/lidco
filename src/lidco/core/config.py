"""Configuration system for LIDCO using Pydantic."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PermissionLevel(str, Enum):
    AUTO = "auto"
    ASK = "ask"
    DENY = "deny"


class ProviderConfig(BaseModel):
    """A single LLM provider endpoint configuration."""

    api_base: str = ""
    api_key: str = ""
    api_type: str = "openai"
    api_version: str = ""
    models: list[str] = Field(default_factory=list)
    default_model: str = ""


class RoleModelConfig(BaseModel):
    """Model assignment for a specific role/agent."""

    model: str
    fallback: str = ""
    temperature: float | None = None
    max_tokens: int | None = None


class LLMProvidersConfig(BaseModel):
    """Top-level LLM providers + role-based model mapping."""

    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    role_models: dict[str, RoleModelConfig] = Field(default_factory=dict)

    def resolve_model(self, role: str) -> RoleModelConfig:
        """Resolve model config for a given role, falling back to 'default'."""
        if role in self.role_models:
            return self.role_models[role]
        return self.role_models.get("default", RoleModelConfig(model="gpt-4o-mini"))

    def resolve_model_name(self, role: str) -> str:
        """Return just the model string for a role."""
        return self.resolve_model(role).model

    def resolve_fallback(self, role: str) -> str:
        """Return the fallback model for a role."""
        cfg = self.resolve_model(role)
        if cfg.fallback:
            return cfg.fallback
        default = self.role_models.get("default")
        if default and default.fallback:
            return default.fallback
        return ""


class RetryConfig(BaseModel):
    """Retry with exponential backoff configuration."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    default_model: str = "gpt-4o-mini"
    temperature: float = 0.1
    max_tokens: int = 4096
    streaming: bool = True
    fallback_models: list[str] = Field(default_factory=lambda: ["gpt-4o-mini"])
    session_token_limit: int = 0  # 0 = unlimited
    retry: RetryConfig = Field(default_factory=RetryConfig)


class CLIConfig(BaseModel):
    """CLI display configuration."""

    theme: str = "monokai"
    show_tool_calls: bool = True
    show_thinking: bool = True
    max_history: int = 1000


class PermissionsConfig(BaseModel):
    """Tool permission levels."""

    auto_allow: list[str] = Field(
        default_factory=lambda: ["file_read", "glob", "grep"]
    )
    ask: list[str] = Field(
        default_factory=lambda: ["file_write", "file_edit", "bash", "git"]
    )
    deny: list[str] = Field(default_factory=list)

    def get_level(self, tool_name: str) -> PermissionLevel:
        if tool_name in self.deny:
            return PermissionLevel.DENY
        if tool_name in self.auto_allow:
            return PermissionLevel.AUTO
        return PermissionLevel.ASK


class AgentsConfig(BaseModel):
    """Agent system configuration."""

    default: str = "coder"
    auto_review: bool = True
    auto_plan: bool = True
    max_review_iterations: int = 2
    parallel_execution: bool = True
    max_iterations: int = 200  # global default, agents can override


class MemoryConfig(BaseModel):
    """Persistent memory configuration."""

    enabled: bool = True
    auto_save: bool = True
    max_entries: int = 500


class RAGConfig(BaseModel):
    """RAG / vector store configuration."""

    enabled: bool = False
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_results: int = 5


class LidcoConfig(BaseModel):
    """Root configuration model."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    llm_providers: LLMProvidersConfig = Field(default_factory=LLMProvidersConfig)
    cli: CLIConfig = Field(default_factory=CLIConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)


class EnvSettings(BaseSettings):
    """Environment variable overrides."""

    model_config = SettingsConfigDict(
        env_prefix="LIDCO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    default_model: str | None = None
    log_level: str = "INFO"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts, override wins on conflicts."""
    result = {**base}
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_yaml_config(path: Path) -> dict[str, Any]:
    """Load a YAML config file, return empty dict if not found."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _resolve_env_vars(value: Any) -> Any:
    """Recursively replace ${ENV_VAR} references with actual env values.

    If an env var is not set, the placeholder is preserved as-is.
    """
    import os
    import re

    if isinstance(value, str):
        pattern = re.compile(r"\$\{(\w+)\}")
        return pattern.sub(
            lambda m: os.environ.get(m.group(1), m.group(0)),
            value,
        )
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def _load_llm_providers(
    package_config_dir: Path,
    global_config_dir: Path,
    project_config_dir: Path,
    project_root: Path,
) -> LLMProvidersConfig:
    """Load llm_providers.yaml with layered precedence + env var resolution.

    Order (later overrides earlier):
      1. configs/llm_providers.yaml        (shipped defaults)
      2. ~/.lidco/llm_providers.yaml       (global user overrides)
      3. .lidco/llm_providers.yaml         (project .lidco/ dir)
      4. <project_root>/llm_providers.yaml (project root — easiest to edit)
    """
    merged: dict[str, Any] = {}
    for config_path in [
        package_config_dir / "llm_providers.yaml",
        global_config_dir / "llm_providers.yaml",
        project_config_dir / "llm_providers.yaml",
        project_root / "llm_providers.yaml",
    ]:
        layer = load_yaml_config(config_path)
        merged = _deep_merge(merged, layer)

    merged = _resolve_env_vars(merged)
    return LLMProvidersConfig(**merged) if merged else LLMProvidersConfig()


def load_config(project_dir: Path | None = None) -> LidcoConfig:
    """Load configuration with layered precedence.

    Order (later overrides earlier):
    1. Built-in defaults (Pydantic defaults)
    2. configs/default.yaml (shipped with package)
    3. ~/.lidco/config.yaml (global user config)
    4. .lidco/config.yaml (project-level config)
    5. Environment variables

    llm_providers.yaml is loaded separately with the same precedence.
    """
    package_config_dir = Path(__file__).parent.parent.parent.parent / "configs"
    global_config_dir = Path.home() / ".lidco"
    project_config_dir = (project_dir or Path.cwd()) / ".lidco"

    merged: dict[str, Any] = {}

    for config_path in [
        package_config_dir / "default.yaml",
        global_config_dir / "config.yaml",
        project_config_dir / "config.yaml",
    ]:
        layer = load_yaml_config(config_path)
        merged = _deep_merge(merged, layer)

    config = LidcoConfig(**merged)

    # Load LLM providers config
    project_root = project_dir or Path.cwd()
    llm_providers = _load_llm_providers(
        package_config_dir, global_config_dir, project_config_dir, project_root
    )
    config = config.model_copy(update={"llm_providers": llm_providers})

    env = EnvSettings()
    if env.default_model:
        config = config.model_copy(
            update={"llm": config.llm.model_copy(update={"default_model": env.default_model})}
        )

    return config
