"""Local model support via Ollama — Task 427.

Provides OllamaProvider for communicating with a locally-running Ollama
instance through its OpenAI-compatible REST API.

Usage::

    provider = OllamaProvider()
    if provider.is_available():
        models = await provider.list_models()
        response = await provider.chat(messages, model="llama3")
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Any

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434"
_TAGS_ENDPOINT = "/api/tags"
_CHAT_ENDPOINT = "/v1/chat/completions"
_TIMEOUT = 5.0  # seconds for availability check
_CHAT_TIMEOUT = 120.0


class OllamaProvider:
    """Communicates with a locally-running Ollama instance.

    Args:
        base_url: Base URL of the Ollama server.
    """

    def __init__(self, base_url: str = _DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        """Check if Ollama is running (synchronous).

        Returns True if the ``/api/tags`` endpoint responds successfully.
        """
        try:
            import urllib.request
            url = self.base_url + _TAGS_ENDPOINT
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def is_available_async(self) -> bool:
        """Async variant of :meth:`is_available`."""
        try:
            import urllib.request
            loop = asyncio.get_event_loop()
            url = self.base_url + _TAGS_ENDPOINT
            return await loop.run_in_executor(None, self._check_tags, url)
        except Exception:
            return False

    def _check_tags(self, url: str) -> bool:
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List models available in the local Ollama instance (synchronous)."""
        try:
            import urllib.request
            url = self.base_url + _TAGS_ENDPOINT
            with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                models_raw = data.get("models", [])
                return [m.get("name", "") for m in models_raw if m.get("name")]
        except Exception as exc:
            logger.debug("list_models failed: %s", exc)
            return []

    async def list_models_async(self) -> list[str]:
        """Async variant of :meth:`list_models`."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.list_models)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any,
    ) -> str:
        """Send a chat completion request and return the assistant message.

        Args:
            messages: List of ``{"role": ..., "content": ...}`` dicts.
            model: Ollama model name (e.g. ``"llama3"``).
            **kwargs: Additional OpenAI-compatible parameters.

        Returns:
            The assistant's reply as a plain string.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        payload.update(kwargs)

        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, self._post_json, _CHAT_ENDPOINT, payload)

        choices = raw.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        model: str,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion response, yielding text chunks.

        Args:
            messages: Conversation messages.
            model: Ollama model name.
            **kwargs: Additional parameters forwarded to the API.

        Yields:
            String chunks of the assistant response.
        """
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        payload.update(kwargs)

        url = self.base_url + _CHAT_ENDPOINT
        import urllib.request

        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        loop = asyncio.get_event_loop()

        def _read_stream() -> list[str]:
            chunks: list[str] = []
            try:
                with urllib.request.urlopen(req, timeout=_CHAT_TIMEOUT) as resp:
                    for line_bytes in resp:
                        line = line_bytes.decode().strip()
                        if not line or not line.startswith("data: "):
                            continue
                        payload_str = line[6:]
                        if payload_str == "[DONE]":
                            break
                        try:
                            obj = json.loads(payload_str)
                            delta = obj.get("choices", [{}])[0].get("delta", {})
                            chunk = delta.get("content", "")
                            if chunk:
                                chunks.append(chunk)
                        except Exception:
                            pass
            except Exception as exc:
                logger.debug("stream_chat error: %s", exc)
            return chunks

        chunks = await loop.run_in_executor(None, _read_stream)
        for chunk in chunks:
            yield chunk

    def _post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Synchronous helper: POST JSON and return parsed response."""
        import urllib.request

        url = self.base_url + endpoint
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=_CHAT_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
