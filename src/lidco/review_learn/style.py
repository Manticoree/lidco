"""Review Style Guide — Team review conventions and feedback templates (Q332, task 1774)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Tone(Enum):
    """Tone for review comments."""

    NEUTRAL = "neutral"
    ENCOURAGING = "encouraging"
    DIRECT = "direct"
    QUESTIONING = "questioning"


@dataclass(frozen=True)
class FeedbackTemplate:
    """A reusable template for review comments."""

    template_id: str
    category: str
    tone: Tone
    template: str
    example: str = ""

    def render(self, **kwargs: str) -> str:
        """Render the template with the given variables."""
        result = self.template
        for key, value in kwargs.items():
            result = result.replace(f"{{{{{key}}}}}", value)
        return result


@dataclass(frozen=True)
class StyleConvention:
    """A team review convention / guideline."""

    name: str
    description: str
    do_examples: tuple[str, ...] = ()
    dont_examples: tuple[str, ...] = ()
    priority: int = 0


@dataclass
class StyleGuide:
    """Manages team review style conventions, tone guidelines, and templates."""

    team_name: str = "default"
    _conventions: dict[str, StyleConvention] = field(default_factory=dict)
    _templates: dict[str, FeedbackTemplate] = field(default_factory=dict)
    default_tone: Tone = Tone.NEUTRAL
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()

    # -- Conventions -------------------------------------------------------

    def add_convention(self, convention: StyleConvention) -> None:
        self._conventions = {**self._conventions, convention.name: convention}

    def remove_convention(self, name: str) -> bool:
        if name not in self._conventions:
            return False
        self._conventions = {k: v for k, v in self._conventions.items() if k != name}
        return True

    def get_convention(self, name: str) -> StyleConvention | None:
        return self._conventions.get(name)

    def list_conventions(self) -> list[StyleConvention]:
        return sorted(self._conventions.values(), key=lambda c: (-c.priority, c.name))

    @property
    def convention_count(self) -> int:
        return len(self._conventions)

    # -- Templates ---------------------------------------------------------

    def add_template(self, template: FeedbackTemplate) -> None:
        self._templates = {**self._templates, template.template_id: template}

    def remove_template(self, template_id: str) -> bool:
        if template_id not in self._templates:
            return False
        self._templates = {k: v for k, v in self._templates.items() if k != template_id}
        return True

    def get_template(self, template_id: str) -> FeedbackTemplate | None:
        return self._templates.get(template_id)

    def list_templates(self, category: str | None = None, tone: Tone | None = None) -> list[FeedbackTemplate]:
        templates = list(self._templates.values())
        if category is not None:
            templates = [t for t in templates if t.category == category]
        if tone is not None:
            templates = [t for t in templates if t.tone == tone]
        return sorted(templates, key=lambda t: t.template_id)

    @property
    def template_count(self) -> int:
        return len(self._templates)

    # -- Rendering ---------------------------------------------------------

    def render_feedback(self, template_id: str, **kwargs: str) -> str | None:
        """Render a feedback template. Returns None if template not found."""
        tmpl = self._templates.get(template_id)
        if tmpl is None:
            return None
        return tmpl.render(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "team_name": self.team_name,
            "default_tone": self.default_tone.value,
            "convention_count": self.convention_count,
            "template_count": self.template_count,
        }


def create_default_style_guide(team_name: str = "default") -> StyleGuide:
    """Create a style guide pre-loaded with common conventions and templates."""
    guide = StyleGuide(team_name=team_name)

    guide.add_convention(StyleConvention(
        name="be-constructive",
        description="Frame feedback as suggestions, not demands",
        do_examples=("Consider using X because...", "What do you think about..."),
        dont_examples=("This is wrong", "You should have..."),
        priority=10,
    ))
    guide.add_convention(StyleConvention(
        name="explain-why",
        description="Always explain the reasoning behind a suggestion",
        do_examples=("This could cause a race condition because...",),
        dont_examples=("Add a lock here",),
        priority=9,
    ))
    guide.add_convention(StyleConvention(
        name="praise-good-code",
        description="Acknowledge well-written code, not just problems",
        do_examples=("Nice use of the builder pattern here!",),
        dont_examples=(),
        priority=5,
    ))

    guide.add_template(FeedbackTemplate(
        template_id="suggest-refactor",
        category="refactoring",
        tone=Tone.QUESTIONING,
        template="What do you think about extracting {{code}} into a separate {{target}}? It might improve readability.",
        example="What do you think about extracting this loop into a separate helper function? It might improve readability.",
    ))
    guide.add_template(FeedbackTemplate(
        template_id="security-concern",
        category="security",
        tone=Tone.DIRECT,
        template="This {{issue}} could be a security risk. Consider {{fix}} to mitigate it.",
        example="This SQL concatenation could be a security risk. Consider using parameterized queries to mitigate it.",
    ))
    guide.add_template(FeedbackTemplate(
        template_id="positive-feedback",
        category="praise",
        tone=Tone.ENCOURAGING,
        template="Great job on {{what}}! This is clean and well-structured.",
        example="Great job on the error handling! This is clean and well-structured.",
    ))

    return guide
