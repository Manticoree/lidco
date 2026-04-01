"""Check model availability per provider."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelStatus(str, Enum):
    """Availability status of a model."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"
    RATE_LIMITED = "RATE_LIMITED"


@dataclass(frozen=True)
class ModelCheck:
    """Result of a model availability check."""

    model: str
    provider: str
    status: ModelStatus = ModelStatus.UNKNOWN
    context_window: int = 0
    message: str = ""


# (provider, context_window)
_KnownModel = tuple[str, int]

_KNOWN_MODELS: dict[str, _KnownModel] = {
    "claude-sonnet-4": ("anthropic", 200_000),
    "claude-opus-4": ("anthropic", 200_000),
    "gpt-4o": ("openai", 128_000),
    "gpt-4o-mini": ("openai", 128_000),
    "gemini-2.5-pro": ("google", 1_000_000),
}

_BUDGET_MAP: dict[str, tuple[str, ...]] = {
    "low": ("gpt-4o-mini",),
    "medium": ("claude-sonnet-4", "gpt-4o"),
    "high": ("claude-opus-4",),
}


class ModelChecker:
    """Look up known models and provide recommendations."""

    def __init__(self) -> None:
        self._known_models: dict[str, _KnownModel] = dict(_KNOWN_MODELS)

    def check_model(self, model: str) -> ModelCheck:
        """Return info for *model* if known, else UNKNOWN."""
        entry = self._known_models.get(model)
        if entry is None:
            return ModelCheck(
                model=model,
                provider="unknown",
                status=ModelStatus.UNKNOWN,
                message=f"Model '{model}' not in known list",
            )
        provider, ctx = entry
        return ModelCheck(
            model=model,
            provider=provider,
            status=ModelStatus.AVAILABLE,
            context_window=ctx,
            message=f"{model} ({provider}, {ctx:,} tokens)",
        )

    def check_all(self) -> list[ModelCheck]:
        """Check every known model."""
        return [self.check_model(m) for m in self._known_models]

    def recommend(self, budget: str = "medium") -> list[ModelCheck]:
        """Return recommended models for the given budget tier."""
        names = _BUDGET_MAP.get(budget, _BUDGET_MAP["medium"])
        return [self.check_model(n) for n in names]

    def summary(self, results: list[ModelCheck]) -> str:
        """One-line summary of model checks."""
        parts: list[str] = []
        for r in results:
            tag = f"[{r.status.value}]"
            parts.append(f"{tag} {r.message}")
        return " | ".join(parts)
