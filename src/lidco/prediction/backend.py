"""PredictionBackend — pluggable backend for next-edit prediction (Ollama / remote / disabled)."""
from __future__ import annotations

import asyncio
import json
import urllib.request
from dataclasses import dataclass
from typing import Callable


@dataclass
class PredictionBackendConfig:
    backend: str = "remote"  # "ollama" | "remote" | "disabled"
    ollama_model: str = "codellama:7b"
    ollama_url: str = "http://localhost:11434"
    remote_model: str = "anthropic/claude-haiku-4-5-20251001"
    timeout: float = 10.0


class PredictionBackend:
    """Route next-edit prediction to Ollama, a remote model, or disable it."""

    def __init__(self, config: PredictionBackendConfig | None = None) -> None:
        self._config = config or PredictionBackendConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def predict(
        self,
        prompt: str,
        max_tokens: int = 300,
        temperature: float = 0.3,
    ) -> str:
        """Return a prediction string or "" if disabled/unavailable."""
        if self._config.backend == "disabled":
            return ""
        if self._config.backend == "ollama":
            try:
                return await self.call_ollama(
                    self._config.ollama_url,
                    self._config.ollama_model,
                    prompt,
                    max_tokens,
                    temperature,
                )
            except Exception:
                return ""
        # remote — stub (no real LLM wired in production stub)
        return ""

    def switch_backend(self, backend: str) -> None:
        """Immutably replace config with the new backend, keeping other fields."""
        self._config = PredictionBackendConfig(
            backend=backend,
            ollama_model=self._config.ollama_model,
            ollama_url=self._config.ollama_url,
            remote_model=self._config.remote_model,
            timeout=self._config.timeout,
        )

    @property
    def active_backend(self) -> str:
        return self._config.backend

    # ------------------------------------------------------------------
    # Ollama
    # ------------------------------------------------------------------

    @staticmethod
    async def call_ollama(
        url: str,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """POST to Ollama /api/generate (non-streaming) in a thread."""

        def _blocking() -> str:
            payload = json.dumps(
                {
                    "model": model,
                    "prompt": prompt,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                    },
                    "stream": False,
                }
            ).encode()
            req = urllib.request.Request(
                f"{url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
            return data["response"]

        return await asyncio.to_thread(_blocking)

    # ------------------------------------------------------------------
    # LLM function factory
    # ------------------------------------------------------------------

    def create_llm_fn(self) -> Callable | None:
        """Return an async callable ``async (prompt) -> str`` or None if disabled."""
        if self._config.backend == "disabled":
            return None

        async def fn(prompt: str) -> str:
            return await self.predict(prompt)

        return fn
