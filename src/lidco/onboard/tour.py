"""Codebase Tour — guided tour of codebase with key files, architecture overview,
interactive navigation, and progress tracking.

Part of Q330 — Onboarding Intelligence (task 1762).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class TourStop:
    """A single stop on the codebase tour."""

    name: str
    path: str
    description: str
    category: str = "general"
    order: int = 0
    highlights: List[str] = field(default_factory=list)


@dataclass
class TourProgress:
    """Tracks which stops have been visited."""

    total: int = 0
    visited: List[str] = field(default_factory=list)

    @property
    def visited_count(self) -> int:
        return len(self.visited)

    @property
    def percent(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.visited_count / self.total * 100, 1)

    @property
    def complete(self) -> bool:
        return self.visited_count >= self.total


@dataclass
class ArchitectureOverview:
    """High-level architecture summary."""

    name: str
    description: str
    layers: List[Dict[str, str]] = field(default_factory=list)
    key_patterns: List[str] = field(default_factory=list)


class CodebaseTour:
    """Guided tour of a codebase with interactive navigation and progress."""

    def __init__(self, root_dir: str = ".") -> None:
        self._root_dir = root_dir
        self._stops: List[TourStop] = []
        self._progress = TourProgress()
        self._categories: Dict[str, List[TourStop]] = {}

    @property
    def root_dir(self) -> str:
        return self._root_dir

    @property
    def stops(self) -> List[TourStop]:
        return list(self._stops)

    @property
    def progress(self) -> TourProgress:
        return TourProgress(
            total=self._progress.total,
            visited=list(self._progress.visited),
        )

    def add_stop(self, stop: TourStop) -> None:
        """Add a stop to the tour."""
        self._stops = [*self._stops, stop]
        cat_list = self._categories.get(stop.category, [])
        self._categories = {
            **self._categories,
            stop.category: [*cat_list, stop],
        }
        self._progress = TourProgress(
            total=len(self._stops),
            visited=list(self._progress.visited),
        )

    def add_stops(self, stops: Sequence[TourStop]) -> None:
        """Add multiple stops."""
        for s in stops:
            self.add_stop(s)

    def visit(self, stop_name: str) -> Optional[TourStop]:
        """Mark a stop as visited and return it."""
        for s in self._stops:
            if s.name == stop_name:
                if stop_name not in self._progress.visited:
                    self._progress = TourProgress(
                        total=self._progress.total,
                        visited=[*self._progress.visited, stop_name],
                    )
                return s
        return None

    def next_stop(self) -> Optional[TourStop]:
        """Return the next unvisited stop."""
        sorted_stops = sorted(self._stops, key=lambda s: s.order)
        for s in sorted_stops:
            if s.name not in self._progress.visited:
                return s
        return None

    def stops_by_category(self, category: str) -> List[TourStop]:
        """Return stops filtered by category."""
        return list(self._categories.get(category, []))

    def categories(self) -> List[str]:
        """Return all category names."""
        return sorted(self._categories.keys())

    def reset(self) -> None:
        """Reset progress."""
        self._progress = TourProgress(total=len(self._stops), visited=[])

    def architecture_overview(self) -> ArchitectureOverview:
        """Generate an architecture overview from the tour stops."""
        layers: List[Dict[str, str]] = []
        seen_cats: Dict[str, bool] = {}
        for s in sorted(self._stops, key=lambda x: x.order):
            if s.category not in seen_cats:
                seen_cats = {**seen_cats, s.category: True}
                layers = [*layers, {"name": s.category, "description": s.description}]
        return ArchitectureOverview(
            name=os.path.basename(self._root_dir) or "project",
            description=f"Architecture overview with {len(layers)} layers",
            layers=layers,
            key_patterns=[s.name for s in self._stops[:5]],
        )

    def key_files(self) -> List[Dict[str, str]]:
        """Return list of key files from tour stops."""
        return [
            {"name": s.name, "path": s.path, "description": s.description}
            for s in sorted(self._stops, key=lambda x: x.order)
        ]

    def summary(self) -> str:
        """Return a human-readable summary."""
        prog = self.progress
        lines = [
            f"Codebase Tour: {os.path.basename(self._root_dir) or 'project'}",
            f"Stops: {prog.total}",
            f"Visited: {prog.visited_count}/{prog.total} ({prog.percent}%)",
        ]
        if prog.complete:
            lines.append("Status: COMPLETE")
        else:
            nxt = self.next_stop()
            if nxt:
                lines.append(f"Next: {nxt.name} — {nxt.description}")
        return "\n".join(lines)
