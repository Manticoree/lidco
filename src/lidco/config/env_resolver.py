"""Q128 — Configuration Profiles: EnvResolver."""
from __future__ import annotations

import os
import re
from typing import Any


class EnvResolver:
    """Resolve ${VAR} and $VAR patterns in config values."""

    _BRACE_RE = re.compile(r"\$\{([^}]+)\}")
    _BARE_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")

    def __init__(self, env: dict | None = None) -> None:
        self._env: dict[str, str] = dict(env) if env is not None else dict(os.environ)

    def set_env(self, key: str, value: str) -> None:
        self._env[key] = value

    def resolve(self, value: str, strict: bool = False) -> str:
        if not isinstance(value, str):
            return value

        def _replace_brace(m: re.Match) -> str:
            var = m.group(1)
            if var in self._env:
                return self._env[var]
            if strict:
                raise KeyError(f"Environment variable '{var}' not found")
            return ""

        def _replace_bare(m: re.Match) -> str:
            var = m.group(1)
            if var in self._env:
                return self._env[var]
            if strict:
                raise KeyError(f"Environment variable '{var}' not found")
            return m.group(0)  # leave as-is for bare $VAR when not found

        result = self._BRACE_RE.sub(_replace_brace, value)
        result = self._BARE_RE.sub(_replace_bare, result)
        return result

    def resolve_dict(self, d: dict) -> dict:
        return {k: self._resolve_value(v) for k, v in d.items()}

    def resolve_list(self, lst: list) -> list:
        return [self._resolve_value(v) for v in lst]

    def _resolve_value(self, v: Any) -> Any:
        if isinstance(v, str):
            return self.resolve(v)
        if isinstance(v, dict):
            return self.resolve_dict(v)
        if isinstance(v, list):
            return self.resolve_list(v)
        return v
