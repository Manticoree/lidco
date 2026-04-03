"""Provider-specific message schema registry."""
from __future__ import annotations

from typing import Any


# Default schemas shipped with the registry.
_OPENAI_SCHEMA: dict[str, Any] = {
    "roles": ["system", "user", "assistant", "tool"],
    "content_types": ["text", "image_url"],
    "required_fields": ["role"],
    "max_content_length": 100_000,
}

_ANTHROPIC_SCHEMA: dict[str, Any] = {
    "roles": ["system", "user", "assistant", "tool"],
    "content_types": ["text", "image", "tool_use", "tool_result"],
    "required_fields": ["role", "content"],
    "max_content_length": 200_000,
}

_DEFAULT_SCHEMA: dict[str, Any] = {
    "roles": ["system", "user", "assistant", "tool"],
    "content_types": ["text"],
    "required_fields": ["role"],
    "max_content_length": 100_000,
}

# Model-name prefix → provider mapping for auto_select.
_PREFIX_MAP: dict[str, str] = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
}


class SchemaRegistry:
    """Registry mapping provider names to message schemas.

    Each schema is a plain dict with keys ``roles``, ``content_types``,
    ``required_fields``, and ``max_content_length``.
    """

    def __init__(self) -> None:
        self._schemas: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, provider: str, schema: dict[str, Any]) -> None:
        """Register (or replace) *schema* for *provider*."""
        self._schemas = {**self._schemas, provider: dict(schema)}

    def get(self, provider: str) -> dict[str, Any] | None:
        """Return the schema for *provider*, or ``None``."""
        schema = self._schemas.get(provider)
        if schema is not None:
            return dict(schema)
        return None

    def has(self, provider: str) -> bool:
        """Return whether *provider* has a registered schema."""
        return provider in self._schemas

    def list_providers(self) -> list[str]:
        """Return sorted list of registered provider names."""
        return sorted(self._schemas)

    def auto_select(self, model: str) -> dict[str, Any]:
        """Select a schema based on *model* name prefix.

        Falls back to a generic default schema when no prefix matches.
        """
        lower = model.lower()
        for prefix, provider in _PREFIX_MAP.items():
            if lower.startswith(prefix):
                schema = self.get(provider)
                if schema is not None:
                    return schema
        return dict(_DEFAULT_SCHEMA)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def with_defaults(cls) -> SchemaRegistry:
        """Return a new registry pre-configured with openai and anthropic schemas."""
        registry = cls()
        registry.register("openai", _OPENAI_SCHEMA)
        registry.register("anthropic", _ANTHROPIC_SCHEMA)
        return registry
