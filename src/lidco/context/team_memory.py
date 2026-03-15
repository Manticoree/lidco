"""Team/org shared memory — Task 311.

Reads and writes ``.lidco/team-memory.md`` (Markdown with YAML frontmatter
sections) as a shared knowledge base committed to the repository.

Format::

    # Team Memory

    ## [key] database-url
    tags: [infrastructure, db]
    description: Production database connection string pattern

    The team uses PostgreSQL 15. Connection pattern: postgresql://user:pass@host/db

    ## [key] code-style
    tags: [style]

    Follow PEP-8. Max line length 100. Use ruff for formatting.

Usage::

    store = TeamMemoryStore()
    store.load()
    store.set("oncall-rotation", "Alice → Bob → Carol")
    store.save()
    entries = store.search("oncall")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_SECTION_RE = re.compile(
    r"^##\s+\[key\]\s+(\S+)\s*\n(.*?)(?=^##\s+\[key\]|\Z)",
    re.MULTILINE | re.DOTALL,
)
_FRONTMATTER_RE = re.compile(r"^(.*?)\n\n(.*)", re.DOTALL)

_DEFAULT_FILE = Path(".lidco") / "team-memory.md"


@dataclass
class TeamMemoryEntry:
    """A single entry in team memory."""

    key: str
    content: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""


class TeamMemoryStore:
    """Loads and persists team memory from a Markdown file.

    Args:
        path: Path to the team-memory.md file. Defaults to ``.lidco/team-memory.md``.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else _DEFAULT_FILE
        self._entries: dict[str, TeamMemoryEntry] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def load(self) -> int:
        """Load entries from the team memory file. Returns count loaded."""
        self._entries.clear()
        if not self._path.exists():
            self._loaded = True
            return 0
        try:
            text = self._path.read_text(encoding="utf-8")
            self._parse(text)
            self._loaded = True
        except Exception as exc:
            logger.warning("TeamMemoryStore: failed to load %s: %s", self._path, exc)
        return len(self._entries)

    def save(self) -> None:
        """Persist the current entries back to the file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self._render(), encoding="utf-8")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def set(
        self,
        key: str,
        content: str,
        tags: list[str] | None = None,
        description: str = "",
    ) -> TeamMemoryEntry:
        """Add or update a team memory entry."""
        entry = TeamMemoryEntry(
            key=key,
            content=content.strip(),
            tags=list(tags or []),
            description=description,
        )
        self._entries[key] = entry
        return entry

    def get(self, key: str) -> TeamMemoryEntry | None:
        """Return entry by key, or None."""
        return self._entries.get(key)

    def delete(self, key: str) -> bool:
        """Remove entry. Returns True if it existed."""
        if key in self._entries:
            del self._entries[key]
            return True
        return False

    def list_entries(self) -> list[TeamMemoryEntry]:
        """Return all entries sorted by key."""
        return sorted(self._entries.values(), key=lambda e: e.key)

    def search(self, query: str) -> list[TeamMemoryEntry]:
        """Return entries matching query (key, content, description, or tag)."""
        q = query.lower()
        return [
            e for e in self._entries.values()
            if q in e.key.lower()
            or q in e.content.lower()
            or q in e.description.lower()
            or any(q in t.lower() for t in e.tags)
        ]

    def count(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _parse(self, text: str) -> None:
        for m in _SECTION_RE.finditer(text):
            key = m.group(1).strip()
            body = m.group(2).strip()
            tags: list[str] = []
            description = ""
            content = body
            # Try to extract YAML frontmatter from the section body
            fm_match = _FRONTMATTER_RE.match(body)
            if fm_match:
                try:
                    meta = yaml.safe_load(fm_match.group(1)) or {}
                    if isinstance(meta, dict):
                        raw_tags = meta.get("tags", [])
                        tags = list(raw_tags) if isinstance(raw_tags, list) else []
                        description = str(meta.get("description", ""))
                        content = fm_match.group(2).strip()
                except Exception:
                    pass
            self._entries[key] = TeamMemoryEntry(
                key=key,
                content=content,
                tags=tags,
                description=description,
            )

    def _render(self) -> str:
        lines = ["# Team Memory\n"]
        for entry in self.list_entries():
            lines.append(f"## [key] {entry.key}")
            meta: dict = {}
            if entry.tags:
                meta["tags"] = entry.tags
            if entry.description:
                meta["description"] = entry.description
            if meta:
                lines.append(yaml.dump(meta, default_flow_style=False).rstrip())
                lines.append("")
            lines.append(entry.content)
            lines.append("")
        return "\n".join(lines)
