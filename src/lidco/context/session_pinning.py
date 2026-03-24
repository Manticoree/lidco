"""Session learning and context pinning — auto-detect important files and context."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PinnedItem:
    content: str                  # file path or text snippet
    kind: str = "text"            # "file" | "text" | "decision"
    source: str = "manual"        # "manual" | "auto"
    access_count: int = 1
    tags: list[str] = field(default_factory=list)


@dataclass
class PinningReport:
    auto_pinned: int
    total_pinned: int
    items: list[PinnedItem]

    def format_summary(self) -> str:
        if not self.items:
            return "No pinned context."
        lines = [f"Pinned context ({self.total_pinned} items, {self.auto_pinned} auto):"]
        for item in self.items[:15]:
            src = "*" if item.source == "auto" else "."
            lines.append(f"  {src} [{item.kind}] {item.content[:70]}")
        return "\n".join(lines)


class SessionPinner:
    """Track important files/decisions and pin them for future sessions.

    Learns which files are most relevant from session activity and
    persists pins to a JSON store for cross-session injection.
    """

    def __init__(self, root: str | Path = ".", store_path: str | None = None) -> None:
        self.root = Path(root).resolve()
        _default = self.root / ".lidco" / "session_pins.json"
        self._store_path = Path(store_path) if store_path else _default
        self._pins: list[PinnedItem] = []
        self._load()

    def _load(self) -> None:
        if self._store_path.exists():
            try:
                data = json.loads(self._store_path.read_text(encoding="utf-8"))
                self._pins = [PinnedItem(**d) for d in data]
            except Exception:
                self._pins = []

    def _save(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        data = [vars(p) for p in self._pins]
        self._store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def pin(self, content: str, kind: str = "text", source: str = "manual", tags: list[str] | None = None) -> PinnedItem:
        """Manually pin a file path or text snippet."""
        # Dedup: if already pinned, increment access_count
        for existing in self._pins:
            if existing.content == content:
                existing.access_count += 1
                self._save()
                return existing
        item = PinnedItem(content=content, kind=kind, source=source, tags=tags or [])
        self._pins = [item] + self._pins  # prepend (most recent first)
        self._save()
        return item

    def unpin(self, content: str) -> bool:
        """Remove a pin by content. Returns True if found."""
        before = len(self._pins)
        self._pins = [p for p in self._pins if p.content != content]
        if len(self._pins) < before:
            self._save()
            return True
        return False

    def get_pinned(self) -> list[PinnedItem]:
        return list(self._pins)

    def auto_pin_from_session(self, session_data: list[dict[str, Any]]) -> int:
        """Infer important files from session activity and auto-pin them.

        Looks at 'file' keys in tool calls, counts access frequency,
        pins top N most-accessed files.

        Returns count of newly pinned items.
        """
        file_counts: dict[str, int] = {}
        for turn in session_data:
            content = str(turn.get("content", ""))
            # Look for file paths mentioned
            for match in re.finditer(r'[\w/.\-]+\.(?:py|ts|js|yaml|json|toml|md)', content):
                path = match.group(0)
                file_counts[path] = file_counts.get(path, 0) + 1
            # Look for explicit file keys
            if "file" in turn:
                p = str(turn["file"])
                file_counts[p] = file_counts.get(p, 0) + 1

        # Pin files accessed >= 2 times
        new_pins = 0
        for path, count in sorted(file_counts.items(), key=lambda x: -x[1]):
            if count < 2:
                continue
            existing = any(p.content == path for p in self._pins)
            if not existing:
                self.pin(path, kind="file", source="auto", tags=["auto-detected"])
                new_pins += 1
            if new_pins >= 10:
                break

        return new_pins

    def infer_important_files(self, session_data: list[dict[str, Any]]) -> list[str]:
        """Return top accessed file paths from session_data without pinning."""
        file_counts: dict[str, int] = {}
        for turn in session_data:
            content = str(turn.get("content", ""))
            for match in re.finditer(r'[\w/.\-]+\.(?:py|ts|js|yaml|json|toml|md)', content):
                path = match.group(0)
                file_counts[path] = file_counts.get(path, 0) + 1
        return [p for p, _ in sorted(file_counts.items(), key=lambda x: -x[1])[:20]]

    def get_report(self) -> PinningReport:
        auto = sum(1 for p in self._pins if p.source == "auto")
        return PinningReport(auto_pinned=auto, total_pinned=len(self._pins), items=list(self._pins))
