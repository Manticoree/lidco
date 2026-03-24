"""Architect-editor split model routing — parity with Aider architect mode."""
from __future__ import annotations

from dataclasses import dataclass, field

# Roles that belong to the "architect" (planning) side
_ARCHITECT_ROLES = frozenset({"planner", "critique", "review", "architect"})
# Roles that belong to the "editor" (code generation) side
_EDITOR_ROLES = frozenset({"executor", "code_gen", "editor", "coder"})


@dataclass
class ArchitectEditorConfig:
    """Model assignments for architect/editor split."""

    architect_model: str | None = None
    editor_model: str | None = None
    default_model: str = "openai/glm-4.7"


@dataclass
class TokenUsage:
    architect_tokens: int = 0
    editor_tokens: int = 0

    def add(self, role: str, tokens: int) -> None:
        if role in _ARCHITECT_ROLES:
            self.architect_tokens += tokens
        else:
            self.editor_tokens += tokens

    @property
    def total(self) -> int:
        return self.architect_tokens + self.editor_tokens


class ArchitectEditorRouter:
    """Routes LLM calls to architect_model or editor_model based on role."""

    def __init__(self, config: ArchitectEditorConfig | None = None) -> None:
        self._config = config or ArchitectEditorConfig()
        self._usage = TokenUsage()

    @property
    def config(self) -> ArchitectEditorConfig:
        return self._config

    @property
    def usage(self) -> TokenUsage:
        return self._usage

    def set_architect_model(self, model: str) -> None:
        self._config = ArchitectEditorConfig(
            architect_model=model,
            editor_model=self._config.editor_model,
            default_model=self._config.default_model,
        )

    def set_editor_model(self, model: str) -> None:
        self._config = ArchitectEditorConfig(
            architect_model=self._config.architect_model,
            editor_model=model,
            default_model=self._config.default_model,
        )

    def get_model(self, role: str) -> str:
        """Return the appropriate model for a given role."""
        if role in _ARCHITECT_ROLES and self._config.architect_model:
            return self._config.architect_model
        if role in _EDITOR_ROLES and self._config.editor_model:
            return self._config.editor_model
        return self._config.default_model

    def record_usage(self, role: str, tokens: int) -> None:
        self._usage.add(role, tokens)

    def summary(self) -> dict:
        return {
            "architect_model": self._config.architect_model,
            "editor_model": self._config.editor_model,
            "default_model": self._config.default_model,
            "architect_tokens": self._usage.architect_tokens,
            "editor_tokens": self._usage.editor_tokens,
            "total_tokens": self._usage.total,
        }
