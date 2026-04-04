"""AnnotationOverlay — render annotations alongside code lines."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.annotations.engine import AnnotationEngine
from lidco.annotations.markers import MarkerRegistry


_GUTTER_ICONS: dict[str, str] = {
    "note": "[i]",
    "warning": "[!]",
    "error": "[X]",
    "todo": "[T]",
    "fixme": "[F]",
    "question": "[?]",
    "review": "[R]",
}


@dataclass(frozen=True)
class OverlayLine:
    """A single line of code with optional annotations and gutter icon."""

    line_number: int
    content: str
    annotations: list[str] = field(default_factory=list)
    gutter_icon: str = ""


class AnnotationOverlay:
    """Combine code lines with annotations for display."""

    def __init__(
        self,
        engine: AnnotationEngine,
        markers: MarkerRegistry | None = None,
    ) -> None:
        self._engine = engine
        self._markers = markers

    def gutter_icon_for(self, category: str) -> str:
        return _GUTTER_ICONS.get(category.lower(), "[*]")

    def render(
        self, file_path: str, code_lines: list[str]
    ) -> list[OverlayLine]:
        file_anns = self._engine.for_file(file_path)
        ann_by_line: dict[int, list[str]] = {}
        cat_by_line: dict[int, str] = {}
        for a in file_anns:
            ann_by_line.setdefault(a.line, []).append(f"[{a.category}] {a.text}")
            cat_by_line.setdefault(a.line, a.category)

        result: list[OverlayLine] = []
        for idx, line in enumerate(code_lines, start=1):
            anns = ann_by_line.get(idx, [])
            icon = self.gutter_icon_for(cat_by_line[idx]) if idx in cat_by_line else ""
            result.append(OverlayLine(
                line_number=idx,
                content=line,
                annotations=anns,
                gutter_icon=icon,
            ))
        return result

    def render_text(
        self, file_path: str, code_lines: list[str]
    ) -> str:
        lines = self.render(file_path, code_lines)
        parts: list[str] = []
        for ol in lines:
            gutter = ol.gutter_icon if ol.gutter_icon else "   "
            parts.append(f"{gutter} {ol.line_number:>4} | {ol.content}")
            for ann in ol.annotations:
                parts.append(f"        ^ {ann}")
        return "\n".join(parts)

    def filter_by_category(
        self, file_path: str, code_lines: list[str], category: str
    ) -> list[OverlayLine]:
        all_lines = self.render(file_path, code_lines)
        # keep lines that have annotations matching category or lines without annotations
        anns_for_cat = {
            a.line
            for a in self._engine.for_file(file_path)
            if a.category == category
        }
        return [ol for ol in all_lines if ol.line_number in anns_for_cat]

    def summary(self) -> dict:
        return {
            "engine_count": self._engine.count(),
            "has_markers": self._markers is not None,
        }
