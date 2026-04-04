"""PresetLibrary — built-in and community presets."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.presets.template import SessionTemplate


@dataclass(frozen=True)
class Preset:
    """An immutable preset wrapping a SessionTemplate."""

    name: str
    category: str
    template: SessionTemplate
    author: str = "system"
    version: str = "1.0"


_BUILTIN_PRESETS: list[tuple[str, str, SessionTemplate]] = [
    (
        "bug-fix",
        "development",
        SessionTemplate(
            name="bug-fix",
            description="Debug and fix bugs efficiently",
            system_prompt="You are a debugging assistant. Focus on root-cause analysis.",
            tools=["read", "edit", "bash", "grep"],
            tags=["debug", "fix"],
        ),
    ),
    (
        "feature",
        "development",
        SessionTemplate(
            name="feature",
            description="Implement new features with TDD",
            system_prompt="You are a feature development assistant. Write tests first.",
            tools=["read", "edit", "bash", "grep", "write"],
            tags=["feature", "tdd"],
        ),
    ),
    (
        "refactor",
        "development",
        SessionTemplate(
            name="refactor",
            description="Refactor code for clarity and performance",
            system_prompt="You are a refactoring assistant. Preserve behavior while improving structure.",
            tools=["read", "edit", "bash", "grep"],
            tags=["refactor", "cleanup"],
        ),
    ),
    (
        "review",
        "quality",
        SessionTemplate(
            name="review",
            description="Review code for quality and correctness",
            system_prompt="You are a code reviewer. Identify issues and suggest improvements.",
            tools=["read", "grep", "bash"],
            tags=["review", "quality"],
        ),
    ),
    (
        "docs",
        "documentation",
        SessionTemplate(
            name="docs",
            description="Write and update documentation",
            system_prompt="You are a documentation assistant. Write clear, concise docs.",
            tools=["read", "edit", "write"],
            tags=["docs", "documentation"],
        ),
    ),
]

_BUILTIN_NAMES: frozenset[str] = frozenset(n for n, _, _ in _BUILTIN_PRESETS)


class PresetLibrary:
    """Library of built-in and user presets."""

    def __init__(self) -> None:
        self._presets: dict[str, Preset] = {}
        for name, category, template in _BUILTIN_PRESETS:
            self._presets[name] = Preset(
                name=name, category=category, template=template
            )

    def get(self, name: str) -> Preset | None:
        """Get preset by name."""
        return self._presets.get(name)

    def by_category(self, category: str) -> list[Preset]:
        """Return presets in the given category."""
        return [p for p in self._presets.values() if p.category == category]

    def add(self, preset: Preset) -> Preset:
        """Add a user preset. Overwrites existing user presets."""
        self._presets[preset.name] = preset
        return preset

    def remove(self, name: str) -> bool:
        """Remove a preset. Cannot remove built-in presets."""
        if name in _BUILTIN_NAMES:
            return False
        if name in self._presets:
            del self._presets[name]
            return True
        return False

    def builtin_names(self) -> list[str]:
        """Return sorted list of built-in preset names."""
        return sorted(_BUILTIN_NAMES)

    def all_presets(self) -> list[Preset]:
        """Return all presets."""
        return list(self._presets.values())

    def categories(self) -> list[str]:
        """Return sorted unique categories."""
        return sorted({p.category for p in self._presets.values()})

    def summary(self) -> dict:
        """Return a summary of the library."""
        return {
            "total": len(self._presets),
            "builtin": len(_BUILTIN_NAMES),
            "user": len(self._presets) - sum(
                1 for n in self._presets if n in _BUILTIN_NAMES
            ),
            "categories": self.categories(),
        }
