"""LiteLLM-based provider supporting 100+ LLM backends."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import litellm

from lidco.llm.base import BaseLLMProvider, LLMResponse, Message, StreamChunk
from lidco.llm.exceptions import LLMRetryExhausted
from lidco.llm.retry import RETRYABLE_EXCEPTIONS, RetryConfig, with_retry

logger = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True
litellm.set_verbose = False
# Use local model cost map to avoid network fetch on startup
import os as _os
import logging as _logging
_os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
# LiteLLM uses both "litellm" and "LiteLLM" logger names
_logging.getLogger("litellm").setLevel(_logging.ERROR)
_logging.getLogger("LiteLLM").setLevel(_logging.ERROR)

_ANTHROPIC_BETA_CACHING = ["prompt-caching-2024-07-31"]

# LiteLLM provider prefixes that route to Anthropic Claude models.
_ANTHROPIC_MODEL_PREFIXES = (
    "claude-",
    "anthropic/",
    "bedrock/anthropic",
    "vertex_ai/claude",
)


def _is_anthropic_model(model: str) -> bool:
    """Return True if the model routes to an Anthropic Claude backend.

    Covers direct Anthropic API (``claude-*``), LiteLLM proxy (``anthropic/*``),
    AWS Bedrock (``bedrock/anthropic.*``), and Google Vertex AI
    (``vertex_ai/claude-*``) prefixes.
    """
    return any(model.startswith(p) for p in _ANTHROPIC_MODEL_PREFIXES)


def _apply_prompt_caching(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Wrap the system message content with cache_control for Anthropic caching.

    Transforms the system message from::

        {"role": "system", "content": "..."}

    to::

        {"role": "system", "content": [{"type": "text", "text": "...",
          "cache_control": {"type": "ephemeral"}}]}

    The system prompt is the primary caching target because it contains the
    static agent instructions and injected project context that repeat every
    iteration.  Non-system messages and system messages whose content is
    already a list (already processed) are passed through unchanged.

    Returns the transformed messages list and the extra_body dict with the
    required anthropic_beta header.
    """
    result = []
    for msg in messages:
        if msg["role"] == "system" and isinstance(msg.get("content"), str):
            cached_msg = {
                **msg,
                "content": [
                    {
                        "type": "text",
                        "text": msg["content"],
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
            result.append(cached_msg)
        else:
            result.append(msg)

    extra_body: dict[str, Any] = {"anthropic_beta": _ANTHROPIC_BETA_CACHING}
    return result, extra_body


def _maybe_apply_caching(kwargs: dict[str, Any]) -> None:
    """Apply prompt prefix caching in-place if the model is an Anthropic model."""
    if _is_anthropic_model(kwargs.get("model", "")):
        kwargs["messages"], extra_body = _apply_prompt_caching(kwargs["messages"])
        kwargs["extra_body"] = {**kwargs.get("extra_body", {}), **extra_body}


def calculate_cost(model: str, usage: dict[str, int]) -> float:
    """Calculate the cost of an LLM call using litellm's pricing data.

    Falls back to :func:`~lidco.core.token_budget.estimate_cost_from_tokens`
    for models not in litellm's registry (e.g. custom providers like GLM).

    Returns 0.0 for unknown models or on any error.
    """
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    try:
        cost = litellm.completion_cost(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        if cost is not None and cost >= 0.0:
            return cost
    except Exception:
        pass
    # Fallback: manual pricing table for custom providers
    from lidco.core.token_budget import estimate_cost_from_tokens
    return estimate_cost_from_tokens(model, prompt_tokens, completion_tokens)


def _messages_to_dicts(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert Message objects to litellm-compatible dicts.

    Compatibility notes:
    - Assistant messages with tool_calls use ``content: null`` (not ``""``) so
      that strict OpenAI-compatible APIs (GLM, Mistral, etc.) accept them.
    - The ``name`` field is omitted from ``tool`` role messages: ``tool_call_id``
      already links each result to its call and many APIs reject the extra field.
    """
    result = []
    for msg in messages:
        d: dict[str, Any] = {"role": msg.role}

        # Use null content for assistant messages that only produce tool calls
        if msg.role == "assistant" and msg.tool_calls and not msg.content:
            d["content"] = None
        else:
            d["content"] = msg.content

        if msg.tool_calls:
            d["tool_calls"] = msg.tool_calls
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        # Omit `name` on tool messages — not supported by all OpenAI-compatible APIs
        if msg.name and msg.role != "tool":
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
        default_model: str = "openai/glm-4.7",
        providers_config: Any | None = None,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self._default_model = default_model
        self._retry_config = retry_config or RetryConfig()
        self._custom_api_bases: dict[str, str] = {}
        self._custom_api_keys: dict[str, str] = {}

        if providers_config is not None:
            self._register_custom_providers(providers_config)

    def set_default_model(self, model: str) -> None:
        """Update the default model without recreating the provider."""
        self._default_model = model

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
        _maybe_apply_caching(kwargs)

        async def _call() -> Any:
            return await litellm.acompletion(**kwargs)

        response = await with_retry(_call, self._retry_config, model_name=kwargs["model"])

        if not response.choices:
            raise ValueError(f"Empty choices in LLM response for model {kwargs['model']!r}")
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
        _maybe_apply_caching(kwargs)

        async def _call() -> Any:
            return await litellm.acompletion(**kwargs)

        response = await with_retry(_call, self._retry_config, model_name=kwargs["model"])

        model_name = kwargs["model"]
        try:
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
        except RETRYABLE_EXCEPTIONS as exc:
            # Mid-stream transient error: re-raise as LLMRetryExhausted so the
            # ModelRouter's fallback chain can try the next model.
            raise LLMRetryExhausted(
                f"Stream from '{model_name}' interrupted: {exc}",
                attempts=[(model_name, exc)],
            ) from exc
        except Exception as exc:
            # Non-retryable stream error (malformed chunk, AttributeError, etc.)
            # Convert to LLMRetryExhausted so ModelRouter can try the next model.
            raise LLMRetryExhausted(
                f"Stream from '{model_name}' failed unexpectedly: {exc}",
                attempts=[(model_name, exc)],
            ) from exc

    def list_models(self) -> list[str]:
        """List available models from litellm's registry."""
        try:
            return litellm.model_list or []
        except Exception:
            return [self._default_model]
