"""PromptAdapter — adapt prompt style to task type with model-specific tuning."""
from __future__ import annotations

from dataclasses import dataclass, field


_DEFAULT_TEMPLATES: dict[str, str] = {
    "code": (
        "You are an expert software engineer. Write clean, well-documented code.\n"
        "Task: {prompt}"
    ),
    "explanation": (
        "You are a clear and patient technical teacher.\n"
        "Explain the following in simple terms:\n{prompt}"
    ),
    "debugging": (
        "You are a meticulous debugger. Analyze the issue step by step.\n"
        "Problem: {prompt}"
    ),
    "refactoring": (
        "You are a refactoring specialist. Improve the code while preserving behaviour.\n"
        "Code to refactor:\n{prompt}"
    ),
    "review": (
        "You are a thorough code reviewer. List issues by severity.\n"
        "Code to review:\n{prompt}"
    ),
}

_MODEL_HINTS: dict[str, dict[str, str]] = {
    "gpt-4": {"prefix": "Be precise and concise.", "suffix": ""},
    "claude": {"prefix": "Think step by step.", "suffix": ""},
    "llama": {"prefix": "Answer directly.", "suffix": ""},
}


@dataclass
class PromptAdapter:
    """Adapt prompts based on task type and target model."""

    templates: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_TEMPLATES))
    model: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def supported_types(self) -> list[str]:
        """Return list of supported task types."""
        return sorted(self.templates.keys())

    def get_template(self, task_type: str) -> str:
        """Return the raw template string for *task_type*.

        Raises ``KeyError`` if *task_type* is unknown.
        """
        if task_type not in self.templates:
            raise KeyError(f"Unknown task type: {task_type!r}")
        return self.templates[task_type]

    def adapt(self, prompt: str, task_type: str) -> str:
        """Adapt *prompt* for the given *task_type*, applying model hints."""
        template = self.get_template(task_type)
        result = template.format(prompt=prompt)
        if self.model:
            hint = self._model_hint()
            if hint:
                result = f"{hint}\n{result}"
        return result

    def add_template(self, task_type: str, template: str) -> None:
        """Register a custom template for *task_type*.

        The template should contain ``{prompt}`` as a placeholder.
        """
        self.templates[task_type] = template

    def remove_template(self, task_type: str) -> bool:
        """Remove a template. Returns ``True`` if it existed."""
        return self.templates.pop(task_type, None) is not None  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _model_hint(self) -> str:
        model_lower = self.model.lower()
        for key, hints in _MODEL_HINTS.items():
            if key in model_lower:
                return hints["prefix"]
        return ""
