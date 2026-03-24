"""Persistent named scratchpads accessible via @notepad:<name> context reference."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Notepad:
    name: str
    content: str
    created_at: float
    updated_at: float
    path: str = ""

    def word_count(self) -> int:
        return len(self.content.split())


class NotepadStore:
    """File-backed store for named notepads in .lidco/notepads/<name>.md."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            base_dir = Path(".lidco") / "notepads"
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        # Sanitize name: allow alphanum, dash, underscore, dot
        safe = "".join(c for c in name if c.isalnum() or c in "-_.")
        if not safe:
            safe = "unnamed"
        return self._base / f"{safe}.md"

    def create(self, name: str, content: str = "") -> Notepad:
        p = self._path(name)
        now = time.time()
        p.write_text(content, encoding="utf-8")
        return Notepad(name=name, content=content, created_at=now, updated_at=now, path=str(p))

    def read(self, name: str) -> Notepad | None:
        p = self._path(name)
        if not p.exists():
            return None
        content = p.read_text(encoding="utf-8", errors="replace")
        stat = p.stat()
        return Notepad(
            name=name,
            content=content,
            created_at=stat.st_ctime,
            updated_at=stat.st_mtime,
            path=str(p),
        )

    def update(self, name: str, content: str) -> Notepad:
        p = self._path(name)
        now = time.time()
        created = p.stat().st_ctime if p.exists() else now
        p.write_text(content, encoding="utf-8")
        return Notepad(name=name, content=content, created_at=created, updated_at=now, path=str(p))

    def delete(self, name: str) -> bool:
        p = self._path(name)
        if p.exists():
            p.unlink()
            return True
        return False

    def list(self) -> list[Notepad]:
        result = []
        for p in sorted(self._base.glob("*.md")):
            name = p.stem
            content = p.read_text(encoding="utf-8", errors="replace")
            stat = p.stat()
            result.append(Notepad(
                name=name,
                content=content,
                created_at=stat.st_ctime,
                updated_at=stat.st_mtime,
                path=str(p),
            ))
        return result

    def exists(self, name: str) -> bool:
        return self._path(name).exists()
