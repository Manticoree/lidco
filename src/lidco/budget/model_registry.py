"""Map model names to context window sizes and capabilities."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    """Immutable descriptor for a single LLM model."""

    name: str
    context_window: int
    max_output: int = 4096
    provider: str = ""
    supports_caching: bool = False
    supports_vision: bool = False
    cost_per_m_input: float = 0.0
    cost_per_m_output: float = 0.0


_BUILTIN_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo("claude-opus-4", 200000, provider="anthropic", supports_caching=True, supports_vision=True),
    ModelInfo("claude-sonnet-4", 200000, provider="anthropic", supports_caching=True, supports_vision=True),
    ModelInfo("claude-haiku-3.5", 200000, provider="anthropic", supports_caching=True, supports_vision=True),
    ModelInfo("gpt-4o", 128000, provider="openai", supports_vision=True),
    ModelInfo("gpt-4o-mini", 128000, provider="openai", supports_vision=True),
    ModelInfo("gpt-4-turbo", 128000, provider="openai", supports_vision=True),
    ModelInfo("gpt-3.5-turbo", 16385, provider="openai"),
    ModelInfo("o1", 200000, provider="openai"),
    ModelInfo("o3", 200000, provider="openai"),
    ModelInfo("deepseek-v3", 128000, provider="deepseek"),
    ModelInfo("gemini-2.5-pro", 1000000, provider="google", supports_vision=True),
    ModelInfo("gemini-2.5-flash", 1000000, provider="google", supports_vision=True),
)


class ModelRegistry:
    """Registry mapping model names to their capabilities."""

    def __init__(self) -> None:
        self._models: dict[str, ModelInfo] = {}
        for info in _BUILTIN_MODELS:
            self._models[info.name] = info

    def register(self, info: ModelInfo) -> None:
        """Add or override a model entry."""
        self._models = {**self._models, info.name: info}

    def get(self, model_name: str) -> ModelInfo | None:
        """Exact match first, then substring match."""
        if model_name in self._models:
            return self._models[model_name]
        for key, info in self._models.items():
            if model_name in key or key in model_name:
                return info
        return None

    def get_context_window(self, model_name: str, default: int = 128000) -> int:
        """Return context window size for *model_name*."""
        info = self.get(model_name)
        return info.context_window if info is not None else default

    def get_max_output(self, model_name: str, default: int = 4096) -> int:
        """Return max output tokens for *model_name*."""
        info = self.get(model_name)
        return info.max_output if info is not None else default

    def list_models(self) -> list[ModelInfo]:
        """Return all registered models."""
        return list(self._models.values())

    def summary(self) -> str:
        """Human-readable summary of all models."""
        if not self._models:
            return "No models registered."
        lines = [f"Model Registry ({len(self._models)} models):"]
        for info in self._models.values():
            lines.append(
                f"  {info.name}: {info.context_window:,} ctx, "
                f"{info.max_output:,} out, provider={info.provider or 'unknown'}"
            )
        return "\n".join(lines)
