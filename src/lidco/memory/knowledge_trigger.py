"""Knowledge trigger — match task context to relevant architectural knowledge (Devin 2.0 parity)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class KnowledgeItem:
    id: str
    title: str
    content: str
    triggers: list[str]    # keywords/patterns that activate this item
    tags: list[str] = field(default_factory=list)
    priority: int = 0      # higher = inject first


@dataclass
class TriggerMatch:
    item: KnowledgeItem
    matched_triggers: list[str]
    relevance: float   # 0.0–1.0


@dataclass
class InjectionContext:
    matches: list[TriggerMatch]
    injected_text: str   # ready-to-inject system prompt addition
    total_chars: int

    def is_empty(self) -> bool:
        return len(self.matches) == 0


class KnowledgeTrigger:
    """Store architectural knowledge items and retrieve them based on task context.

    Knowledge items are stored in `.lidco/knowledge/` YAML/JSON files.
    When a task prompt is evaluated, matching items are returned for injection.
    """

    def __init__(
        self,
        store_path: str | Path | None = None,
        max_inject_chars: int = 4000,
    ) -> None:
        self._store = Path(store_path) if store_path else Path(".lidco/knowledge")
        self._items: list[KnowledgeItem] = []
        self.max_inject_chars = max_inject_chars
        self._load()

    def _load(self) -> None:
        if not self._store.exists():
            return
        for f in self._store.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for d in data:
                        self._items.append(KnowledgeItem(**d))
                else:
                    self._items.append(KnowledgeItem(**data))
            except Exception:
                pass

    def add(self, item: KnowledgeItem) -> None:
        """Add a knowledge item to the in-memory store."""
        self._items.append(item)

    def save(self) -> None:
        """Persist all items to the store directory."""
        self._store.mkdir(parents=True, exist_ok=True)
        data = [vars(i) for i in self._items]
        (self._store / "items.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    def match(self, context: str) -> list[TriggerMatch]:
        """Return knowledge items triggered by context string."""
        context_lower = context.lower()
        matches: list[TriggerMatch] = []
        for item in self._items:
            matched: list[str] = []
            for trigger in item.triggers:
                # Support simple glob-like patterns: *keyword*
                pattern = re.escape(trigger.strip("*")).replace(r"\*", ".*")
                if re.search(pattern, context_lower, re.IGNORECASE):
                    matched.append(trigger)
            if matched:
                relevance = min(len(matched) / max(len(item.triggers), 1), 1.0)
                matches.append(TriggerMatch(item=item, matched_triggers=matched, relevance=relevance))
        return sorted(matches, key=lambda m: (-m.item.priority, -m.relevance))

    def build_injection(self, context: str) -> InjectionContext:
        """Build a ready-to-inject text block for the most relevant knowledge items."""
        matches = self.match(context)
        if not matches:
            return InjectionContext(matches=[], injected_text="", total_chars=0)

        sections: list[str] = ["## Relevant architectural knowledge\n"]
        total = len(sections[0])
        used_matches: list[TriggerMatch] = []

        for m in matches:
            chunk = f"### {m.item.title}\n{m.item.content}\n\n"
            if total + len(chunk) > self.max_inject_chars:
                break
            sections.append(chunk)
            total += len(chunk)
            used_matches.append(m)

        injected = "".join(sections).strip()
        return InjectionContext(matches=used_matches, injected_text=injected, total_chars=total)

    def list_items(self) -> list[KnowledgeItem]:
        return list(self._items)

    def remove(self, item_id: str) -> bool:
        before = len(self._items)
        self._items = [i for i in self._items if i.id != item_id]
        return len(self._items) < before
