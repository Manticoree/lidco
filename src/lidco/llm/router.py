"""Model router with fallback and role-based model selection."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from lidco.core.config import LLMProvidersConfig, RoleModelConfig
from lidco.llm.base import BaseLLMProvider, LLMResponse, Message, StreamChunk
from lidco.llm.exceptions import LLMRetryExhausted

logger = logging.getLogger(__name__)


class ModelRouter(BaseLLMProvider):
    """Routes requests to LLM with automatic fallback on failure.

    Supports role-based model selection: each agent role (coder, reviewer, ...)
    can be mapped to a different model via ``LLMProvidersConfig.role_models``.
    """

    def __init__(
        self,
        provider: BaseLLMProvider,
        default_model: str,
        fallback_models: list[str] | None = None,
        llm_providers: LLMProvidersConfig | None = None,
    ) -> None:
        self._provider = provider
        self._default_model = default_model
        self._fallback_models = fallback_models or []
        self._llm_providers = llm_providers or LLMProvidersConfig()
        # Optional callback: (failed_model, fallback_model, reason) -> None
        self._fallback_callback: Any | None = None

    def set_fallback_callback(self, callback: Any) -> None:
        """Set a callback fired when the router falls back to a different model.

        Signature: ``callback(failed: str, fallback: str, reason: str) -> None``.
        """
        self._fallback_callback = callback

    def _notify_fallback(self, failed: str, fallback: str, reason: str) -> None:
        if self._fallback_callback is not None:
            try:
                self._fallback_callback(failed, fallback, reason)
            except Exception:
                pass

    def set_default_model(self, model: str) -> None:
        """Update the default model on both the router and its underlying provider."""
        self._default_model = model
        self._provider.set_default_model(model)

    # ── Role-based resolution ───────────────────────────────────────────────

    def resolve_for_role(self, role: str) -> RoleModelConfig:
        """Return the full model config for a role (agent name or special key).

        Special roles: ``default``, ``routing``, ``completion``.
        """
        return self._llm_providers.resolve_model(role)

    def model_for_role(self, role: str) -> str:
        """Return just the model name for a role."""
        return self._llm_providers.resolve_model_name(role)

    # ── Fallback chain ──────────────────────────────────────────────────────

    def _get_model_chain(self, model: str | None, role: str | None = None) -> list[str]:
        """Build ordered list of models to try.

        Priority:
        1. Explicit ``model`` argument (if provided)
        2. Role-based model from llm_providers.yaml (if role provided)
        3. Default model from LLMConfig
        + fallback from role config
        + global fallback_models
        """
        # Determine primary model
        if model:
            primary = model
        elif role and self._llm_providers.role_models:
            primary = self._llm_providers.resolve_model_name(role)
        else:
            primary = self._default_model

        chain = [primary]

        # Add role-specific fallback
        if role:
            role_fallback = self._llm_providers.resolve_fallback(role)
            if role_fallback and role_fallback not in chain:
                chain.append(role_fallback)

        # Add global fallbacks
        for fb in self._fallback_models:
            if fb not in chain:
                chain.append(fb)

        return chain

    # ── LLM calls ───────────────────────────────────────────────────────────

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        role: str | None = None,
    ) -> LLMResponse:
        """Complete with automatic fallback and optional role-based selection.

        If ``role`` is provided and ``model`` is not, the model is resolved
        from the role_models mapping in llm_providers.yaml.  Temperature and
        max_tokens from the role config are used as defaults (explicit args
        still override).
        """
        # Apply role-level defaults for temperature/max_tokens
        if role and not model:
            role_cfg = self.resolve_for_role(role)
            if temperature is None and role_cfg.temperature is not None:
                temperature = role_cfg.temperature
            if max_tokens is None and role_cfg.max_tokens is not None:
                max_tokens = role_cfg.max_tokens

        chain = self._get_model_chain(model, role=role)
        all_attempts: list[tuple[str, Exception]] = []

        for i, candidate in enumerate(chain):
            try:
                return await self._provider.complete(
                    messages,
                    model=candidate,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                )
            except LLMRetryExhausted as e:
                all_attempts.extend(e.attempts)
                logger.warning(
                    "Model %s exhausted retries: %s. Trying next.", candidate, e
                )
                if i + 1 < len(chain):
                    self._notify_fallback(candidate, chain[i + 1], "retries exhausted")

        raise LLMRetryExhausted(
            f"All {len(chain)} model(s) in the fallback chain failed. "
            f"Tried: {chain}",
            attempts=all_attempts,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        role: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream with automatic fallback and optional role-based selection."""
        if role and not model:
            role_cfg = self.resolve_for_role(role)
            if temperature is None and role_cfg.temperature is not None:
                temperature = role_cfg.temperature
            if max_tokens is None and role_cfg.max_tokens is not None:
                max_tokens = role_cfg.max_tokens

        chain = self._get_model_chain(model, role=role)
        all_attempts: list[tuple[str, Exception]] = []

        for i, candidate in enumerate(chain):
            try:
                async for chunk in self._provider.stream(
                    messages,
                    model=candidate,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                ):
                    yield chunk
                return
            except LLMRetryExhausted as e:
                all_attempts.extend(e.attempts)
                logger.warning(
                    "Model %s exhausted retries (stream): %s. Trying next.",
                    candidate, e,
                )
                if i + 1 < len(chain):
                    self._notify_fallback(candidate, chain[i + 1], "retries exhausted")
            except Exception as e:
                all_attempts.append((candidate, e))
                logger.warning(
                    "Model %s stream error: %s. Trying next.",
                    candidate, e,
                )
                if i + 1 < len(chain):
                    self._notify_fallback(candidate, chain[i + 1], "stream error")

        raise LLMRetryExhausted(
            f"All {len(chain)} model(s) in the fallback chain failed (stream). "
            f"Tried: {chain}",
            attempts=all_attempts,
        )

    def list_models(self) -> list[str]:
        """List available models."""
        return self._provider.list_models()
