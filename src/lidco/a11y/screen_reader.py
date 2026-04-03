"""ARIA-like annotations for terminal; structured output; navigation landmarks."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


_VALID_LANDMARK_TYPES = frozenset(
    {"banner", "navigation", "main", "complementary", "contentinfo"}
)


@dataclass(frozen=True)
class Landmark:
    """A navigation landmark."""

    id: str
    type: str
    label: str
    content: str = ""


@dataclass(frozen=True)
class Annotation:
    """An ARIA-like annotation for a UI element."""

    element_id: str
    role: str
    label: str
    description: str = ""


class ScreenReaderSupport:
    """ARIA-like annotations for terminal output."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._landmarks: list[Landmark] = []
        self._annotations: dict[str, Annotation] = {}

    # -- landmark management --------------------------------------------------

    def add_landmark(self, type: str, label: str, content: str = "") -> Landmark:
        if type not in _VALID_LANDMARK_TYPES:
            raise ValueError(
                f"Invalid landmark type {type!r}. "
                f"Must be one of {sorted(_VALID_LANDMARK_TYPES)}"
            )
        lm = Landmark(id=uuid.uuid4().hex[:12], type=type, label=label, content=content)
        self._landmarks.append(lm)
        return lm

    def remove_landmark(self, landmark_id: str) -> bool:
        for i, lm in enumerate(self._landmarks):
            if lm.id == landmark_id:
                self._landmarks.pop(i)
                return True
        return False

    # -- annotation -----------------------------------------------------------

    def annotate(
        self,
        element_id: str,
        role: str,
        label: str,
        description: str = "",
    ) -> Annotation:
        ann = Annotation(
            element_id=element_id, role=role, label=label, description=description
        )
        self._annotations[element_id] = ann
        return ann

    # -- queries --------------------------------------------------------------

    def get_structure(self) -> list[Landmark]:
        return list(self._landmarks)

    def render_text(self) -> str:
        if not self._enabled:
            return ""
        lines: list[str] = []
        for lm in self._landmarks:
            lines.append(f"[{lm.type}] {lm.label}")
            if lm.content:
                lines.append(f"  {lm.content}")
        for ann in self._annotations.values():
            desc = f" - {ann.description}" if ann.description else ""
            lines.append(f"({ann.role}) {ann.label}{desc}")
        return "\n".join(lines)

    # -- enable / disable -----------------------------------------------------

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def is_enabled(self) -> bool:
        return self._enabled

    # -- summary --------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "enabled": self._enabled,
            "landmarks": len(self._landmarks),
            "annotations": len(self._annotations),
        }
