"""LiteLLM-based provider supporting 100+ LLM backends."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import litellm

from lidco.llm.base import BaseLLMProvider, LLMResponse, Message, StreamChunk
from lidco.llm.retry import RetryConfig, with_retry

logger = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True


def calculate_cost(model: str, usage: dict[str, int]) -> float:
    """Calculate the cost of an LLM call using litellm's pricing data.

    Returns 0.0 for unknown models or on any error.
    """
    try:
        return litellm.completion_cost(
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
    except Exception:
        return 0.0


def _messages_to_dicts(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert Message objects to litellm-compatible dicts."""
    result = []
    for msg in messages:
        d: dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.tool_calls:
            d["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        if msg.name:
            d["name"] = msg.name
        result.append(d)
    return result


class LiteLLMProvider(BaseLLMProvider):
    """Provider using litellm for universal LLM access.

    Supports: OpenAI, Anthropic, Ollama, Groq, Azure, Bedrock,
    Vertex AI, Cohere, Mistral, and 100+ more.

    Custom providers defined in ``llm_providers.yaml`` are registered
    with litellm at init time so that their models resolve correctly.
    """

    def __init__(
        self,
        default_model: str = "gpt-4o-mini",
        providers_config: Any | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self._default_model = default_model
        self._retry_config = retry_config or RetryConfig()
        self._custom_api_bases: dict[str, str] = {}
        self._custom_api_keys: dict[str, str] = {}

        if providers_config is not None:
            self._register_custom_providers(providers_config)

    def _register_custom_providers(self, providers_config: Any) -> None:
        """Register custom provider endpoints with litellm.

        For providers with a custom ``api_base`` we store the mapping so we
        can inject ``api_base`` / ``api_key`` at call time.
        """
        for name, prov in providers_config.providers.items():
            if not prov.api_base:
                continue

            for model_id in prov.models:
                self._custom_api_bases[model_id] = prov.api_base
                if prov.api_key:
                    self._custom_api_keys[model_id] = prov.api_key

            logger.info(
                "Registered custom provider '%s' at %s with %d models",
                name,
                prov.api_base,
                len(prov.models),
            )

    def _resolve_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Inject api_base / api_key for custom provider models."""
        model = kwargs.get("model", "")
        if model in self._custom_api_bases:
            kwargs["api_base"] = self._custom_api_bases[model]
        if model in self._custom_api_keys:
            kwargs["api_key"] = self._custom_api_keys[model]
        return kwargs

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
    ) -> LLMResponse:
        """Send messages to the LLM and get a complete response."""
        kwargs: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": _messages_to_dicts(messages),
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        kwargs = self._resolve_kwargs(kwargs)

        async def _call() -> Any:
            return await litellm.acompletion(**kwargs)

        response = await with_retry(_call, self._retry_config)

        choice = response.choices[0]
        tool_calls_raw = []
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            tool_calls_raw = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        usage = {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
            "completion_tokens": getattr(response.usage, "completion_tokens", 0),
            "total_tokens": getattr(response.usage, "total_tokens", 0),
        }
        resolved_model = response.model or kwargs["model"]
        cost = calculate_cost(resolved_model, usage)

        return LLMResponse(
            content=choice.message.content or "",
            model=resolved_model,
            tool_calls=tool_calls_raw,
            usage=usage,
            finish_reason=choice.finish_reason or "stop",
            cost_usd=cost,
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
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from the LLM."""
        kwargs: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": _messages_to_dicts(messages),
            "stream": True,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        kwargs = self._resolve_kwargs(kwargs)
        # Request usage info in the final streaming chunk
        kwargs["stream_options"] = {"include_usage": True}

        async def _call() -> Any:
            return await litellm.acompletion(**kwargs)

        response = await with_retry(_call, self._retry_config)

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                # Some providers send a usage-only chunk with no choices
                chunk_usage = {}
                if hasattr(chunk, "usage") and chunk.usage:
                    chunk_usage = {
                        "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                        "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                    }
                    yield StreamChunk(usage=chunk_usage)
                continue

            tool_calls_raw = []
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                tool_calls_raw = [
                    {
                        "index": tc.index,
                        "id": getattr(tc, "id", None),
                        "type": "function",
                        "function": {
                            "name": getattr(tc.function, "name", None),
                            "arguments": getattr(tc.function, "arguments", ""),
                        },
                    }
                    for tc in delta.tool_calls
                ]

            chunk_usage = {}
            if hasattr(chunk, "usage") and chunk.usage:
                chunk_usage = {
                    "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(chunk.usage, "completion_tokens", 0),
                    "total_tokens": getattr(chunk.usage, "total_tokens", 0),
                }

            yield StreamChunk(
                content=delta.content or "",
                tool_calls=tool_calls_raw,
                finish_reason=chunk.choices[0].finish_reason,
                usage=chunk_usage,
            )

    def list_models(self) -> list[str]:
        """List available models from litellm's registry."""
        try:
            return litellm.model_list or []
        except Exception:
            return [self._default_model]
