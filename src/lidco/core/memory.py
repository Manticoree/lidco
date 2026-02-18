"""Persistent memory system for cross-session knowledge."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryEntry:
    """A single memory entry."""

    key: str
    content: str
    category: str = "general"  # general, pattern, decision, preference, solution
    tags: tuple[str, ...] = ()
    created_at: str = ""
    source: str = ""  # which project/session created this

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "content": self.content,
            "category": self.category,
            "tags": list(self.tags),
            "created_at": self.created_at or datetime.now(timezone.utc).isoformat(),
            "source": self.source,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> MemoryEntry:
        return MemoryEntry(
            key=data["key"],
            content=data["content"],
            category=data.get("category", "general"),
            tags=tuple(data.get("tags", [])),
            created_at=data.get("created_at", ""),
            source=data.get("source", ""),
        )


class MemoryStore:
    """File-based persistent memory store.

    Stores memories in JSON files organized by category.
    Supports both global (~/.lidco/memory/) and project-level (.lidco/memory/).
    """

    def __init__(
        self,
        global_dir: Path | None = None,
        project_dir: Path | None = None,
        max_entries: int = 500,
    ) -> None:
        self._global_dir = global_dir or (Path.home() / ".lidco" / "memory")
        self._project_dir = project_dir
        self._max_entries = max_entries
        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load memories from disk."""
        for directory in self._get_dirs():
            if not directory.exists():
                continue
            for json_file in directory.glob("*.json"):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    entries = data if isinstance(data, list) else [data]
                    for entry_data in entries:
                        entry = MemoryEntry.from_dict(entry_data)
                        self._entries[entry.key] = entry
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Failed to load memory from %s: %s", json_file, e)

        # Also load MEMORY.md if it exists
        for directory in self._get_dirs():
            md_path = directory / "MEMORY.md"
            if md_path.exists():
                content = md_path.read_text(encoding="utf-8").strip()
                if content:
                    self._entries["__memory_md__"] = MemoryEntry(
                        key="__memory_md__",
                        content=content,
                        category="general",
                        source="MEMORY.md",
                    )

    def _get_dirs(self) -> list[Path]:
        """Get all memory directories (global + project)."""
        dirs = [self._global_dir]
        if self._project_dir:
            dirs.append(self._project_dir / ".lidco" / "memory")
        return dirs

    def _save_entry(self, entry: MemoryEntry, scope: str = "global") -> None:
        """Save a single entry to disk."""
        if scope == "project" and self._project_dir:
            directory = self._project_dir / ".lidco" / "memory"
        else:
            directory = self._global_dir

        directory.mkdir(parents=True, exist_ok=True)
        file_path = directory / f"{entry.category}.json"

        # Load existing entries for this category
        existing: list[dict[str, Any]] = []
        if file_path.exists():
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                existing = data if isinstance(data, list) else [data]
            except json.JSONDecodeError:
                existing = []

        # Update or append
        found = False
        for i, e in enumerate(existing):
            if e.get("key") == entry.key:
                existing[i] = entry.to_dict()
                found = True
                break
        if not found:
            existing.append(entry.to_dict())

        # Enforce max entries per file
        if len(existing) > self._max_entries:
            existing = existing[-self._max_entries :]

        file_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add(
        self,
        key: str,
        content: str,
        *,
        category: str = "general",
        tags: list[str] | None = None,
        source: str = "",
        scope: str = "global",
    ) -> MemoryEntry:
        """Add or update a memory entry."""
        entry = MemoryEntry(
            key=key,
            content=content,
            category=category,
            tags=tuple(tags or []),
            created_at=datetime.now(timezone.utc).isoformat(),
            source=source,
        )
        self._entries[key] = entry
        self._save_entry(entry, scope=scope)
        return entry

    def get(self, key: str) -> MemoryEntry | None:
        """Get a memory entry by key."""
        return self._entries.get(key)

    def search(
        self,
        query: str,
        *,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Search memories by content, category, or tags."""
        query_lower = query.lower()
        results: list[MemoryEntry] = []

        for entry in self._entries.values():
            if entry.key == "__memory_md__":
                continue

            if category and entry.category != category:
                continue

            if tags and not any(t in entry.tags for t in tags):
                continue

            if query_lower in entry.content.lower() or query_lower in entry.key.lower():
                results.append(entry)

            if len(results) >= limit:
                break

        return results

    def remove(self, key: str) -> bool:
        """Remove a memory entry."""
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def list_all(self, category: str | None = None) -> list[MemoryEntry]:
        """List all memory entries, optionally filtered by category."""
        entries = [
            e for e in self._entries.values()
            if e.key != "__memory_md__"
        ]
        if category:
            entries = [e for e in entries if e.category == category]
        return entries

    def build_context_string(self, max_lines: int = 200) -> str:
        """Build a memory context string for injection into system prompts."""
        parts: list[str] = []

        # MEMORY.md first
        md_entry = self._entries.get("__memory_md__")
        if md_entry:
            parts.append(f"## Persistent Memory\n{md_entry.content}")

        # Then categorized entries
        by_category: dict[str, list[MemoryEntry]] = {}
        for entry in self._entries.values():
            if entry.key == "__memory_md__":
                continue
            by_category.setdefault(entry.category, []).append(entry)

        for cat, entries in sorted(by_category.items()):
            parts.append(f"\n### {cat.title()}")
            for entry in entries[-5:]:  # last 20 per category
                tags_str = f" [{', '.join(entry.tags)}]" if entry.tags else ""
                parts.append(f"- **{entry.key}**{tags_str}: {entry.content}")

        full_text = "\n".join(parts)
        lines = full_text.splitlines()
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines.append("\n... (memory truncated)")

        return "\n".join(lines)
