"""Model router with fallback and role-based model selection."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from lidco.core.config import LLMProvidersConfig, RoleModelConfig
from lidco.llm.base import BaseLLMProvider, LLMResponse, Message, StreamChunk

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
        last_error: Exception | None = None

        for candidate in chain:
            try:
                return await self._provider.complete(
                    messages,
                    model=candidate,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice=tool_choice,
                )
            except Exception as e:
                last_error = e
                logger.warning("Model %s failed: %s. Trying next.", candidate, e)

        raise RuntimeError(
            f"All models failed. Last error: {last_error}"
        ) from last_error

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
        last_error: Exception | None = None

        for candidate in chain:
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
            except Exception as e:
                last_error = e
                logger.warning("Model %s failed: %s. Trying next.", candidate, e)

        raise RuntimeError(
            f"All models failed. Last error: {last_error}"
        ) from last_error

    def list_models(self) -> list[str]:
        """List available models."""
        return self._provider.list_models()
