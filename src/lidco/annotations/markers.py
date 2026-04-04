"""MarkerRegistry — built-in and custom code markers with priority."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Marker:
    """A code marker type (e.g. TODO, FIXME)."""

    name: str
    prefix: str
    priority: int = 0
    color: str = ""
    description: str = ""


_BUILTINS: list[Marker] = [
    Marker(name="TODO", prefix="TODO", priority=2, description="Task to complete"),
    Marker(name="FIXME", prefix="FIXME", priority=3, description="Bug or issue to fix"),
    Marker(name="NOTE", prefix="NOTE", priority=0, description="Informational note"),
    Marker(name="WARNING", prefix="WARNING", priority=2, description="Potential issue"),
    Marker(name="QUESTION", prefix="QUESTION", priority=1, description="Needs clarification"),
    Marker(name="REVIEW", prefix="REVIEW", priority=1, description="Needs review"),
]


class MarkerRegistry:
    """Registry for built-in and custom markers."""

    def __init__(self) -> None:
        self._markers: dict[str, Marker] = {}
        self._builtin_names: set[str] = set()
        for m in _BUILTINS:
            self._markers[m.name] = m
            self._builtin_names.add(m.name)

    def register(self, marker: Marker) -> Marker:
        self._markers[marker.name] = marker
        return marker

    def get(self, name: str) -> Marker | None:
        return self._markers.get(name)

    def remove(self, name: str) -> bool:
        if name in self._builtin_names:
            return False
        return self._markers.pop(name, None) is not None

    def all_markers(self) -> list[Marker]:
        return sorted(self._markers.values(), key=lambda m: m.priority, reverse=True)

    def by_priority(self, min_priority: int = 0) -> list[Marker]:
        return sorted(
            [m for m in self._markers.values() if m.priority >= min_priority],
            key=lambda m: m.priority,
            reverse=True,
        )

    def scan_text(self, text: str) -> list[dict]:
        results: list[dict] = []
        lines = text.splitlines()
        for idx, line in enumerate(lines, start=1):
            for marker in self._markers.values():
                pattern = re.compile(re.escape(marker.prefix) + r"[:\s]+(.*)", re.IGNORECASE)
                match = pattern.search(line)
                if match:
                    results.append({
                        "marker": marker.name,
                        "line": idx,
                        "text": match.group(1).strip(),
                    })
        return results

    def builtin_names(self) -> list[str]:
        return sorted(self._builtin_names)

    def summary(self) -> dict:
        return {
            "total": len(self._markers),
            "builtin": len(self._builtin_names),
            "custom": len(self._markers) - len(self._builtin_names),
            "markers": [m.name for m in self.all_markers()],
        }
