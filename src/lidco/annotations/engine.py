"""AnnotationEngine — virtual inline annotations per file/line."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Annotation:
    """A single inline annotation attached to a file and line."""

    id: str
    file_path: str
    line: int
    text: str
    category: str = "note"
    author: str = "system"
    created_at: float = field(default_factory=time.time)


class AnnotationEngine:
    """Add, remove, query, and export inline annotations."""

    def __init__(self) -> None:
        self._annotations: dict[str, Annotation] = {}

    # ---- mutators --------------------------------------------------------

    def add(
        self,
        file_path: str,
        line: int,
        text: str,
        category: str = "note",
        author: str = "system",
    ) -> Annotation:
        ann = Annotation(
            id=uuid.uuid4().hex[:12],
            file_path=file_path,
            line=line,
            text=text,
            category=category,
            author=author,
        )
        self._annotations[ann.id] = ann
        return ann

    def remove(self, annotation_id: str) -> bool:
        return self._annotations.pop(annotation_id, None) is not None

    # ---- queries ---------------------------------------------------------

    def get(self, annotation_id: str) -> Annotation | None:
        return self._annotations.get(annotation_id)

    def for_file(self, file_path: str) -> list[Annotation]:
        return sorted(
            [a for a in self._annotations.values() if a.file_path == file_path],
            key=lambda a: a.line,
        )

    def for_line(self, file_path: str, line: int) -> list[Annotation]:
        return [
            a
            for a in self._annotations.values()
            if a.file_path == file_path and a.line == line
        ]

    def by_category(self, category: str) -> list[Annotation]:
        return [a for a in self._annotations.values() if a.category == category]

    def all_annotations(self) -> list[Annotation]:
        return list(self._annotations.values())

    def count(self) -> int:
        return len(self._annotations)

    def clear(self, file_path: str | None = None) -> int:
        if file_path is None:
            n = len(self._annotations)
            self._annotations.clear()
            return n
        ids = [a.id for a in self._annotations.values() if a.file_path == file_path]
        for aid in ids:
            del self._annotations[aid]
        return len(ids)

    # ---- export / summary ------------------------------------------------

    def export(self, format: str = "json") -> str:
        items = [
            {
                "id": a.id,
                "file_path": a.file_path,
                "line": a.line,
                "text": a.text,
                "category": a.category,
                "author": a.author,
                "created_at": a.created_at,
            }
            for a in self._annotations.values()
        ]
        if format == "json":
            return json.dumps(items, indent=2)
        # csv fallback
        if not items:
            return "id,file_path,line,text,category,author"
        header = "id,file_path,line,text,category,author"
        rows = [header]
        for i in items:
            rows.append(f"{i['id']},{i['file_path']},{i['line']},{i['text']},{i['category']},{i['author']}")
        return "\n".join(rows)

    def summary(self) -> dict:
        cats: dict[str, int] = {}
        files: set[str] = set()
        for a in self._annotations.values():
            cats[a.category] = cats.get(a.category, 0) + 1
            files.add(a.file_path)
        return {
            "total": len(self._annotations),
            "files": len(files),
            "categories": cats,
        }
