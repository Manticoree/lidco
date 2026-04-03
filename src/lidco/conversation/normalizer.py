"""Message normalizer — transforms messages to match a target provider schema."""
from __future__ import annotations

from typing import Any

from lidco.conversation.schema_registry import SchemaRegistry


class MessageNormalizer:
    """Normalize conversation messages to a target provider schema.

    All transformations are **immutable** — input dicts are never mutated.

    Parameters
    ----------
    schema_registry:
        Optional :class:`SchemaRegistry`.  When omitted a default registry
        (``SchemaRegistry.with_defaults()``) is used.
    target_provider:
        Initial target provider name.  Defaults to ``"openai"``.
    """

    def __init__(
        self,
        schema_registry: SchemaRegistry | None = None,
        *,
        target_provider: str = "openai",
    ) -> None:
        self._registry = schema_registry or SchemaRegistry.with_defaults()
        self._target_provider = target_provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_target_provider(self, provider: str) -> None:
        """Change the target provider used for normalization."""
        self._target_provider = provider

    @property
    def target_provider(self) -> str:
        return self._target_provider

    def normalize(self, message: dict[str, Any]) -> dict[str, Any]:
        """Return a **new** dict with the message normalized to the target schema."""
        schema = self._registry.get(self._target_provider)
        if schema is None:
            schema = self._registry.auto_select("")

        result: dict[str, Any] = {}

        # Ensure role
        result["role"] = message.get("role", "user")

        # Normalize content
        content = message.get("content")
        if isinstance(content, str):
            result["content"] = [{"type": "text", "text": content}]
        elif isinstance(content, list):
            result["content"] = [dict(block) if isinstance(block, dict) else block for block in content]
        elif content is None:
            result["content"] = None
        else:
            result["content"] = content

        # Carry over allowed fields
        allowed_extra = {"tool_call_id", "tool_calls", "name", "function_call"}
        for key in allowed_extra:
            if key in message:
                result[key] = message[key]

        # Strip fields not supported by schema
        supported_fields = set(schema.get("required_fields", []))
        supported_fields.update(allowed_extra)
        supported_fields.update({"role", "content"})
        result = {k: v for k, v in result.items() if k in supported_fields}

        return result

    def normalize_batch(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize a list of messages, returning a new list."""
        return [self.normalize(msg) for msg in messages]
