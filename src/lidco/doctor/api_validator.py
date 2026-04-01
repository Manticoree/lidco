"""Validate API keys and provider connectivity."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import re


class KeyStatus(str, Enum):
    """Status of an API key."""

    VALID = "VALID"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    MISSING = "MISSING"
    UNTESTED = "UNTESTED"


@dataclass(frozen=True)
class ApiKeyResult:
    """Result of an API key validation."""

    provider: str
    status: KeyStatus
    key_prefix: str = ""
    message: str = ""


# Provider name -> (env var, regex pattern)
_PROVIDERS: tuple[tuple[str, str, str], ...] = (
    ("anthropic", "ANTHROPIC_API_KEY", r"^sk-ant-"),
    ("openai", "OPENAI_API_KEY", r"^sk-"),
    ("google", "GOOGLE_API_KEY", r"^AI"),
)


class ApiValidator:
    """Check API keys for known LLM providers."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _mask(key: str) -> str:
        """Return first 8 chars followed by '...'."""
        if len(key) <= 8:
            return key
        return key[:8] + "..."

    def check_env_key(self, var_name: str, provider: str) -> ApiKeyResult:
        """Check whether *var_name* is set and matches expected format."""
        value = os.environ.get(var_name, "")
        if not value:
            return ApiKeyResult(
                provider=provider,
                status=KeyStatus.MISSING,
                message=f"{var_name} not set",
            )

        # Find the expected pattern for this provider
        pattern: str | None = None
        for prov, env, pat in _PROVIDERS:
            if prov == provider:
                pattern = pat
                break

        prefix = self._mask(value)
        if pattern and not re.match(pattern, value):
            return ApiKeyResult(
                provider=provider,
                status=KeyStatus.INVALID,
                key_prefix=prefix,
                message=f"{var_name} format invalid",
            )

        return ApiKeyResult(
            provider=provider,
            status=KeyStatus.VALID,
            key_prefix=prefix,
            message=f"{var_name} present",
        )

    def validate_anthropic(self) -> ApiKeyResult:
        """Validate ANTHROPIC_API_KEY."""
        return self.check_env_key("ANTHROPIC_API_KEY", "anthropic")

    def validate_openai(self) -> ApiKeyResult:
        """Validate OPENAI_API_KEY."""
        return self.check_env_key("OPENAI_API_KEY", "openai")

    def validate_all(self) -> list[ApiKeyResult]:
        """Check all known providers."""
        return [
            self.check_env_key(env, prov)
            for prov, env, _ in _PROVIDERS
        ]

    def has_any_key(self) -> bool:
        """Return True if at least one provider key is valid."""
        return any(r.status == KeyStatus.VALID for r in self.validate_all())

    def summary(self, results: list[ApiKeyResult]) -> str:
        """One-line summary of key statuses."""
        parts: list[str] = []
        for r in results:
            tag = f"[{r.status.value}]"
            parts.append(f"{tag} {r.provider}: {r.message}")
        return " | ".join(parts)
