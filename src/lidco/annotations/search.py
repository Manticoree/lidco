"""AnnotationSearch — search, group, bulk-ops on annotations."""
from __future__ import annotations

import json
from dataclasses import dataclass

from lidco.annotations.engine import Annotation, AnnotationEngine


@dataclass(frozen=True)
class SearchResult:
    """A single search hit with relevance score."""

    annotation: Annotation
    relevance: float = 1.0


class AnnotationSearch:
    """Search and aggregate annotations from an AnnotationEngine."""

    def __init__(self, engine: AnnotationEngine) -> None:
        self._engine = engine

    def search(self, query: str, limit: int = 50) -> list[SearchResult]:
        q = query.lower()
        results: list[SearchResult] = []
        for ann in self._engine.all_annotations():
            text_lower = ann.text.lower()
            if q in text_lower:
                # simple relevance: exact-start > contains
                relevance = 1.0 if text_lower.startswith(q) else 0.5
                results.append(SearchResult(annotation=ann, relevance=relevance))
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:limit]

    def by_file(self) -> dict[str, list[Annotation]]:
        grouped: dict[str, list[Annotation]] = {}
        for ann in self._engine.all_annotations():
            grouped.setdefault(ann.file_path, []).append(ann)
        return grouped

    def by_category(self) -> dict[str, list[Annotation]]:
        grouped: dict[str, list[Annotation]] = {}
        for ann in self._engine.all_annotations():
            grouped.setdefault(ann.category, []).append(ann)
        return grouped

    def by_author(self) -> dict[str, list[Annotation]]:
        grouped: dict[str, list[Annotation]] = {}
        for ann in self._engine.all_annotations():
            grouped.setdefault(ann.author, []).append(ann)
        return grouped

    def bulk_remove(
        self, category: str | None = None, file_path: str | None = None
    ) -> int:
        to_remove: list[str] = []
        for ann in self._engine.all_annotations():
            match = True
            if category is not None and ann.category != category:
                match = False
            if file_path is not None and ann.file_path != file_path:
                match = False
            if match:
                to_remove.append(ann.id)
        removed = 0
        for aid in to_remove:
            if self._engine.remove(aid):
                removed += 1
        return removed

    def export(self, format: str = "json") -> str:
        return self._engine.export(format)

    def stats(self) -> dict:
        by_file: dict[str, int] = {}
        by_cat: dict[str, int] = {}
        by_author: dict[str, int] = {}
        for ann in self._engine.all_annotations():
            by_file[ann.file_path] = by_file.get(ann.file_path, 0) + 1
            by_cat[ann.category] = by_cat.get(ann.category, 0) + 1
            by_author[ann.author] = by_author.get(ann.author, 0) + 1
        return {
            "total": self._engine.count(),
            "by_file": by_file,
            "by_category": by_cat,
            "by_author": by_author,
        }

    def summary(self) -> dict:
        s = self.stats()
        return {
            "total": s["total"],
            "files": len(s["by_file"]),
            "categories": len(s["by_category"]),
            "authors": len(s["by_author"]),
        }
