"""
Config Manager — layered configuration with JSON/TOML/INI support.

Layer priority (highest wins):
  1. Environment variables (prefix-based)
  2. Project config (.lidco/config.json or .lidco/config.toml)
  3. User config (~/.lidco/config.json)
  4. System defaults (provided at init)

Features:
- Dot-notation key access (e.g., "llm.model")
- Type coercion (str→int, str→bool, str→float)
- Environment variable override with prefix (e.g., LIDCO_LLM_MODEL)
- JSON and TOML (stdlib tomllib in 3.11+) formats
- Reload config files without restart
- Save changes back to project config

Stdlib only.
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (immutable, returns new dict)."""
    result = deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = deepcopy(val)
    return result


def _get_nested(data: dict, keys: list[str]) -> Any:
    """Get a nested value by key path list. Raises KeyError if not found."""
    cur = data
    for k in keys:
        if not isinstance(cur, dict):
            raise KeyError(k)
        cur = cur[k]
    return cur


def _set_nested(data: dict, keys: list[str], value: Any) -> dict:
    """Return a new dict with the nested key set to value (immutable)."""
    result = deepcopy(data)
    cur = result
    for k in keys[:-1]:
        cur.setdefault(k, {})
        cur = cur[k]
    cur[keys[-1]] = value
    return result


def _coerce(value: str, type_hint: type | None = None) -> Any:
    """Coerce a string value to an appropriate Python type."""
    if type_hint is not None:
        try:
            return type_hint(value)
        except (ValueError, TypeError):
            return value

    # Auto-coerce
    low = value.lower()
    if low in ("true", "yes", "1", "on"):
        return True
    if low in ("false", "no", "0", "off"):
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


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_toml(path: Path) -> dict:
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except ImportError:
        pass
    try:
        import tomli  # optional dep
        return tomli.loads(path.read_text(encoding="utf-8"))  # type: ignore[attr-defined]
    except ImportError:
        pass
    return {}


def _load_file(path: Path) -> dict:
    if path.suffix == ".toml":
        return _load_toml(path)
    return _load_json(path)


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class ConfigManager:
    """
    Layered configuration manager.

    Parameters
    ----------
    defaults : dict | None
        Base default values (lowest priority).
    project_root : str | None
        Root of the project for .lidco/config.* lookup.
    user_home : str | None
        Override home directory for ~/.lidco/config.* lookup.
    env_prefix : str
        Environment variable prefix (default "LIDCO").
        E.g. LIDCO_LLM_MODEL → {"llm": {"model": value}}.
    config_filename : str
        Config filename (without extension) inside .lidco/ directories.
    """

    def __init__(
        self,
        defaults: dict | None = None,
        project_root: str | None = None,
        user_home: str | None = None,
        env_prefix: str = "LIDCO",
        config_filename: str = "config",
    ) -> None:
        self._defaults: dict = defaults or {}
        self._project_root = Path(project_root) if project_root else Path.cwd()
        self._user_home = Path(user_home) if user_home else Path.home()
        self._env_prefix = env_prefix.upper().rstrip("_") + "_"
        self._config_filename = config_filename

        # Runtime overrides (set via .set())
        self._runtime: dict = {}

        # Merged config cache
        self._config: dict = {}
        self.reload()

    # ------------------------------------------------------------------
    # Public API — Read
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a config value by dot-notation key.

        Parameters
        ----------
        key : str
            Dot-separated key, e.g. "llm.model" or "debug".
        default : Any
            Returned if key not found.
        """
        keys = key.split(".")
        try:
            return _get_nested(self._config, keys)
        except (KeyError, TypeError):
            return default

    def get_required(self, key: str) -> Any:
        """Get a config value, raising KeyError if not found."""
        result = self.get(key, ...)
        if result is ...:
            raise KeyError(f"Required config key not found: {key!r}")
        return result

    def __getitem__(self, key: str) -> Any:
        result = self.get(key, ...)
        if result is ...:
            raise KeyError(key)
        return result

    def all(self) -> dict:
        """Return a copy of the full merged config."""
        return deepcopy(self._config)

    # ------------------------------------------------------------------
    # Public API — Write
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any) -> None:
        """
        Set a runtime override (in-memory only, not persisted).

        Parameters
        ----------
        key : str
            Dot-separated key.
        value : Any
            New value.
        """
        keys = key.split(".")
        self._runtime = _set_nested(self._runtime, keys, value)
        self._config = _deep_merge(self._config, _set_nested({}, keys, value))

    def save(self, path: str | Path | None = None) -> Path:
        """
        Persist the runtime overrides to the project config file.

        Parameters
        ----------
        path : str | Path | None
            Explicit save path. Defaults to .lidco/config.json in project root.
        """
        save_path = Path(path) if path else self._project_config_path(".json")
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing project config and merge runtime on top
        existing: dict = {}
        if save_path.exists():
            existing = _load_file(save_path)
        merged = _deep_merge(existing, self._runtime)

        save_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        return save_path

    # ------------------------------------------------------------------
    # Reload
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-read all config files and rebuild the merged config."""
        # Start with defaults
        merged = deepcopy(self._defaults)

        # User config (~/.lidco/config.*)
        user_cfg = self._load_user_config()
        merged = _deep_merge(merged, user_cfg)

        # Project config (.lidco/config.*)
        proj_cfg = self._load_project_config()
        merged = _deep_merge(merged, proj_cfg)

        # Environment variables
        env_cfg = self._load_env_vars()
        merged = _deep_merge(merged, env_cfg)

        # Runtime overrides (highest)
        merged = _deep_merge(merged, self._runtime)

        self._config = merged

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _project_config_path(self, ext: str = ".json") -> Path:
        return self._project_root / ".lidco" / f"{self._config_filename}{ext}"

    def _load_user_config(self) -> dict:
        for ext in (".toml", ".json"):
            p = self._user_home / ".lidco" / f"{self._config_filename}{ext}"
            if p.exists():
                return _load_file(p)
        return {}

    def _load_project_config(self) -> dict:
        for ext in (".toml", ".json"):
            p = self._project_config_path(ext)
            if p.exists():
                return _load_file(p)
        return {}

    def _load_env_vars(self) -> dict:
        """Convert LIDCO_* env vars to nested dict."""
        result: dict = {}
        prefix_len = len(self._env_prefix)
        for k, v in os.environ.items():
            if k.startswith(self._env_prefix):
                key_part = k[prefix_len:].lower()
                keys = key_part.split("_")
                coerced = _coerce(v)
                result = _set_nested(result, keys, coerced)
        return result
