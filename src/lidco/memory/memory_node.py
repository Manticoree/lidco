"""Q130 — Agent Memory Graph: MemoryNode and MemoryEdge."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryNode:
    id: str
    content: str
    node_type: str  # "fact" / "concept" / "event" / "relation"
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: str = ""
    updated_at: str = ""


@dataclass
class MemoryEdge:
    source_id: str
    target_id: str
    relation: str  # "causes" / "related_to" / "part_of" / "implies"
    weight: float = 1.0
