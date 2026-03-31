"""Configuration system for LIDCO using Pydantic."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Canonical .lidco/ directory layout — single source of truth for all paths
# ---------------------------------------------------------------------------

CONFIG_DIR = ".lidco"
CONFIG_FILE = ".lidco/config.yaml"
GLOBAL_CONFIG = "~/.lidco/config.yaml"
MEMORY_DB = ".lidco/agent_memory.db"
CHECKPOINTS_FILE = ".lidco/checkpoints.json"
APPROVAL_QUEUE_FILE = ".lidco/approval_queue.json"
SESSION_HISTORY_FILE = ".lidco/session_history.json"
EVENT_STORE_FILE = ".lidco/event_store.json"
KV_STORE_FILE = ".lidco/kv_store.json"
SNAPSHOTS_DIR = ".lidco/workspace_snapshots"


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
        return self.role_models.get("default", RoleModelConfig(model="openai/glm-4.7"))

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

    default_model: str = "openai/glm-4.7"
    temperature: float = 0.1
    max_tokens: int = 4096
    streaming: bool = True
    fallback_models: list[str] = Field(default_factory=lambda: ["openai/glm-4.7"])
    session_token_limit: int = 0  # 0 = unlimited
    retry: RetryConfig = Field(default_factory=RetryConfig)
    ollama_base_url: str = "http://localhost:11434"  # Q63: local Ollama endpoint
    architect_model: str | None = None  # T451: model for architect (planning) roles
    editor_model: str | None = None  # T451: model for editor (code generation) roles


class CLIConfig(BaseModel):
    """CLI display configuration."""

    theme: str = "monokai"
    show_tool_calls: bool = True
    show_thinking: bool = True
    max_history: int = 1000


class PermissionsConfig(BaseModel):
    """Tool permission levels."""

    # Legacy simple lists (kept for backward compatibility)
    auto_allow: list[str] = Field(
        default_factory=lambda: ["file_read", "glob", "grep"]
    )
    ask: list[str] = Field(
        default_factory=lambda: ["file_write", "file_edit", "bash", "git"]
    )
    deny: list[str] = Field(default_factory=list)

    # New permission engine fields
    mode: str = "default"  # default | accept_edits | plan | dont_ask | bypass
    allow_rules: list[str] = Field(default_factory=list)   # e.g. ["Bash(pytest *)", "FileRead(**)"]
    ask_rules: list[str] = Field(default_factory=list)      # e.g. ["Bash(git *)"]
    deny_rules: list[str] = Field(default_factory=list)     # e.g. ["Bash(git push *)", "FileWrite(.env)"]

    # Task 252: pre-approved command patterns (expanded to Bash(pattern) allow rules)
    command_allowlist: list[str] = Field(
        default_factory=lambda: [
            "pytest *",
            "python -m pytest *",
            "git status",
            "git diff *",
            "git log *",
            "git show *",
            "ruff check *",
            "ruff format *",
            "mypy *",
            "python -m ruff *",
            "python -m mypy *",
        ]
    )

    def get_level(self, tool_name: str) -> PermissionLevel:
        if tool_name in self.deny:
            return PermissionLevel.DENY
        if tool_name in self.auto_allow:
            return PermissionLevel.AUTO
        return PermissionLevel.ASK


class SandboxConfig(BaseModel):
    """Shell execution sandbox configuration."""

    enabled: bool = False
    writable_roots: list[str] = Field(default_factory=list)  # empty = CWD only
    blocked_paths: list[str] = Field(
        default_factory=lambda: [".git", ".lidco"]
    )
    network_access: bool = True
    allowed_domains: list[str] = Field(default_factory=list)  # empty = all


class AgentsConfig(BaseModel):
    """Agent system configuration."""

    default: str = "coder"
    auto_review: bool = True
    auto_plan: bool = True
    max_review_iterations: int = 2
    parallel_execution: bool = True
    max_parallel_agents: int = 3  # maximum concurrent agents in a parallel group
    max_iterations: int = 200  # global default, agents can override
    agent_timeout: int = 0  # seconds; 0 = no timeout
    plan_critique: bool = True  # run auto-critique LLM pass before plan approval
    plan_revise: bool = True  # run planner revision pass after critique before approval
    plan_max_revisions: int = 1  # extra re-critique/revise rounds after initial revision (0 = none)
    plan_memory: bool = True  # save approved plans and retrieve similar ones as warm-start context
    preplan_snapshot: bool = True  # auto-inject git log + coverage before planner starts
    preplan_ambiguity: bool = True  # run cheap LLM pass to surface ambiguities before planner
    debug_mode: bool = False  # enable debug mode (full tracebacks, active error context injection)
    debug_hypothesis: bool = True  # generate ranked hypotheses for debugger agent before execution
    debug_fast_path: bool = True   # try fast fix for SyntaxError/ImportError/NameError before full debug
    auto_debug: bool = False  # auto-trigger debugger when 3+ consecutive errors from same file
    debug_preset: str = "balanced"  # fast | balanced | thorough | silent
    coverage_gap_inject: bool = True  # inject coverage gap context into debugger system prompt
    sbfl_inject: bool = True  # inject Ochiai SBFL suspicious-line ranking into debugger context
    web_context_inject: bool = False  # inject live web search results into pre-planning context (opt-in: network calls)
    web_auto_route: bool = True  # auto-route research-intent messages to researcher agent
    regression_on_save: bool = False  # run related tests when a file is saved
    suggestions_enabled: bool = False  # show next-action suggestions after each agent response
    security_scan_on_save: bool = False  # run security scanner when a file is saved
    # Q63 — Cost & Model Optimization
    extended_thinking: bool = False  # enable Anthropic extended thinking blocks
    thinking_budget: int = 10000  # max thinking tokens when extended_thinking is on
    adaptive_budget: bool = False  # dynamically adjust max_tokens per prompt complexity
    auto_warm: bool = False  # pre-warm Anthropic prompt cache on session start
    # Q72 — Confidence + Next-Edit Prediction
    clarification_threshold: float = 0.7  # confidence below this triggers a clarification ask
    autonomy_mode: str = "supervised"  # autonomous | supervised | interactive


class MemoryConfig(BaseModel):
    """Persistent memory configuration."""

    enabled: bool = True
    auto_save: bool = True
    max_entries: int = 500
    ttl_days: int | None = None  # None = never expire


class RAGConfig(BaseModel):
    """RAG / vector store configuration."""

    enabled: bool = False
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_results: int = 5
    query_expansion: bool = False  # generate alternative phrasings before retrieval (+latency)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    format: str = "pretty"  # "pretty" | "json"
    level: str = "INFO"
    log_file: str = ""  # empty = no file logging


class IndexConfig(BaseModel):
    """Project structural index configuration."""

    auto_watch: bool = False  # auto-reindex on file changes


class MultimodalConfig(BaseModel):
    """Multimodal (voice, image, diagram) configuration."""

    voice_model: str = "base"      # Whisper model name (local) or "api"
    voice_timeout: int = 10        # recording duration in seconds


class LidcoConfig(BaseModel):
    """Root configuration model."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    llm_providers: LLMProvidersConfig = Field(default_factory=LLMProvidersConfig)
    cli: CLIConfig = Field(default_factory=CLIConfig)
    permissions: PermissionsConfig = Field(default_factory=PermissionsConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    index: IndexConfig = Field(default_factory=IndexConfig)
    multimodal: MultimodalConfig = Field(default_factory=MultimodalConfig)
    # MCP server connections — loaded separately from .lidco/mcp.json
    # Not part of the main config file; field kept here for session wiring.
    mcp_enabled: bool = True  # global switch to enable/disable MCP integration
    git_auto_commit: bool = False  # T446: auto-commit dirty files after each agent execution
    diff_first: bool = False  # T446: show diff before committing
    predict_next_edit: bool = False  # T451: enable next-edit prediction


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


_SECTION_NAMES: frozenset[str] = frozenset(
    {"llm", "cli", "permissions", "sandbox", "agents", "memory", "rag", "logging", "index"}
    # Note: "llm_providers" is intentionally absent — it is loaded separately
    # via _load_llm_providers() with its own multi-file precedence chain and
    # cannot be overridden with LIDCO_<SECTION>_<FIELD> env vars.
)


def _coerce_env_value(value: str) -> Any:
    """Coerce a raw env-var string to bool, int, float, or str."""
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _apply_env_overrides(config: LidcoConfig) -> LidcoConfig:
    """Apply ``LIDCO_<SECTION>_<FIELD>`` env vars as config overrides.

    Examples::

        LIDCO_LLM_DEFAULT_MODEL=gpt-4o       → config.llm.default_model
        LIDCO_AGENTS_AUTO_REVIEW=false        → config.agents.auto_review
        LIDCO_RAG_ENABLED=true               → config.rag.enabled
        LIDCO_MEMORY_MAX_ENTRIES=200         → config.memory.max_entries
        LIDCO_CLI_THEME=dracula              → config.cli.theme
    """
    import os

    section_fields: dict[str, dict[str, Any]] = {}

    for env_key, raw_value in os.environ.items():
        if not env_key.startswith("LIDCO_"):
            continue
        remainder = env_key[len("LIDCO_"):].lower()

        for section in _SECTION_NAMES:
            prefix = section + "_"
            if remainder.startswith(prefix):
                field = remainder[len(prefix):]
                section_fields.setdefault(section, {})[field] = _coerce_env_value(raw_value)
                break

    if not section_fields:
        return config

    updates: dict[str, Any] = {}
    for section, fields in section_fields.items():
        sub = getattr(config, section)
        try:
            updates[section] = sub.model_copy(update=fields)
        except Exception:
            # Ignore fields that don't exist on the sub-config
            valid = {k: v for k, v in fields.items() if hasattr(sub, k)}
            if valid:
                updates[section] = sub.model_copy(update=valid)

    return config.model_copy(update=updates) if updates else config


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

    # Apply LIDCO_<SECTION>_<FIELD> env-var overrides (12-factor style)
    config = _apply_env_overrides(config)

    # Legacy: LIDCO_DEFAULT_MODEL (without section prefix) — kept for back-compat
    env = EnvSettings()
    if env.default_model and not any(
        k.upper().startswith("LIDCO_LLM_") for k in os.environ
    ):
        config = config.model_copy(
            update={"llm": config.llm.model_copy(update={"default_model": env.default_model})}
        )

    return config
