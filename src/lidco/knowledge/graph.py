"""Q329 — Knowledge Graph: entities, relationships, traversal, query."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EntityType(Enum):
    """Types of entities in the knowledge graph."""

    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    CONCEPT = "concept"
    PATTERN = "pattern"
    RULE = "rule"


class RelationType(Enum):
    """Types of relationships between entities."""

    CONTAINS = "contains"
    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"
    DEFINES = "defines"
    USES = "uses"


@dataclass
class Entity:
    """A node in the knowledge graph."""

    id: str
    name: str
    entity_type: EntityType
    description: str = ""
    source_file: str = ""
    line_number: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def matches(self, query: str) -> float:
        """Score how well this entity matches a query (0.0–1.0)."""
        q = query.lower()
        if q == self.name.lower():
            return 1.0
        score = 0.0
        if q in self.name.lower():
            score = max(score, 0.8)
        if q in self.description.lower():
            score = max(score, 0.6)
        if any(q in t.lower() for t in self.tags):
            score = max(score, 0.5)
        return score


@dataclass(frozen=True)
class Relationship:
    """An edge in the knowledge graph."""

    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResult:
    """Result of a graph query."""

    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def relationship_count(self) -> int:
        return len(self.relationships)


class KnowledgeGraph:
    """Directed graph of code entities and their relationships."""

    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._relationships: list[Relationship] = []
        self._outgoing: dict[str, list[Relationship]] = {}
        self._incoming: dict[str, list[Relationship]] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_entity(self, entity: Entity) -> None:
        """Add or replace an entity."""
        self._entities[entity.id] = entity
        if entity.id not in self._outgoing:
            self._outgoing[entity.id] = []
        if entity.id not in self._incoming:
            self._incoming[entity.id] = []

    def add_relationship(self, rel: Relationship) -> None:
        """Add a relationship between two existing entities."""
        if rel.source_id not in self._entities:
            raise KeyError(f"Source entity '{rel.source_id}' not in graph")
        if rel.target_id not in self._entities:
            raise KeyError(f"Target entity '{rel.target_id}' not in graph")
        self._relationships.append(rel)
        self._outgoing.setdefault(rel.source_id, []).append(rel)
        self._incoming.setdefault(rel.target_id, []).append(rel)

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity and all its relationships."""
        if entity_id not in self._entities:
            return False
        del self._entities[entity_id]
        self._relationships = [
            r
            for r in self._relationships
            if r.source_id != entity_id and r.target_id != entity_id
        ]
        self._outgoing.pop(entity_id, None)
        self._incoming.pop(entity_id, None)
        for eid in list(self._outgoing):
            self._outgoing[eid] = [
                r for r in self._outgoing[eid] if r.target_id != entity_id
            ]
        for eid in list(self._incoming):
            self._incoming[eid] = [
                r for r in self._incoming[eid] if r.source_id != entity_id
            ]
        return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def all_entities(self) -> list[Entity]:
        return list(self._entities.values())

    def all_relationships(self) -> list[Relationship]:
        return list(self._relationships)

    def neighbors(self, entity_id: str) -> list[Entity]:
        """All entities directly connected (outgoing + incoming)."""
        ids: set[str] = set()
        for r in self._outgoing.get(entity_id, []):
            ids.add(r.target_id)
        for r in self._incoming.get(entity_id, []):
            ids.add(r.source_id)
        return [self._entities[eid] for eid in ids if eid in self._entities]

    def outgoing(self, entity_id: str) -> list[Relationship]:
        return list(self._outgoing.get(entity_id, []))

    def incoming(self, entity_id: str) -> list[Relationship]:
        return list(self._incoming.get(entity_id, []))

    def find_by_type(self, entity_type: EntityType) -> list[Entity]:
        return [e for e in self._entities.values() if e.entity_type == entity_type]

    def find_by_tag(self, tag: str) -> list[Entity]:
        return [e for e in self._entities.values() if tag in e.tags]

    def find_related(
        self, entity_id: str, relation_type: RelationType
    ) -> list[Entity]:
        """Entities connected via a specific relation type."""
        ids: set[str] = set()
        for r in self._outgoing.get(entity_id, []):
            if r.relation_type == relation_type:
                ids.add(r.target_id)
        for r in self._incoming.get(entity_id, []):
            if r.relation_type == relation_type:
                ids.add(r.source_id)
        return [self._entities[eid] for eid in ids if eid in self._entities]

    # ------------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------------

    def shortest_path(self, from_id: str, to_id: str) -> list[str]:
        """BFS shortest path returning entity IDs, or [] if unreachable."""
        if from_id not in self._entities or to_id not in self._entities:
            return []
        if from_id == to_id:
            return [from_id]
        visited: set[str] = {from_id}
        queue: deque[list[str]] = deque([[from_id]])
        while queue:
            path = queue.popleft()
            current = path[-1]
            for neighbor in self.neighbors(current):
                if neighbor.id in visited:
                    continue
                new_path = [*path, neighbor.id]
                if neighbor.id == to_id:
                    return new_path
                visited.add(neighbor.id)
                queue.append(new_path)
        return []

    def subgraph(self, root_id: str, depth: int = 2) -> QueryResult:
        """BFS from root up to *depth* hops, return entities and relationships."""
        root = self._entities.get(root_id)
        if root is None:
            return QueryResult()
        visited: set[str] = {root_id}
        frontier: list[str] = [root_id]
        entities: list[Entity] = [root]
        rels: list[Relationship] = []
        for _ in range(depth):
            next_frontier: list[str] = []
            for eid in frontier:
                for r in self._outgoing.get(eid, []):
                    if r.target_id not in visited:
                        visited.add(r.target_id)
                        target = self._entities.get(r.target_id)
                        if target:
                            entities.append(target)
                            next_frontier.append(r.target_id)
                    rels.append(r)
                for r in self._incoming.get(eid, []):
                    if r.source_id not in visited:
                        visited.add(r.source_id)
                        source = self._entities.get(r.source_id)
                        if source:
                            entities.append(source)
                            next_frontier.append(r.source_id)
                    rels.append(r)
            frontier = next_frontier
        # Deduplicate rels
        seen_rels: set[tuple[str, str, str]] = set()
        unique_rels: list[Relationship] = []
        for r in rels:
            key = (r.source_id, r.target_id, r.relation_type.value)
            if key not in seen_rels:
                seen_rels.add(key)
                unique_rels.append(r)
        return QueryResult(entities=entities, relationships=unique_rels)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        for e in self._entities.values():
            key = e.entity_type.value
            type_counts[key] = type_counts.get(key, 0) + 1
        rel_counts: dict[str, int] = {}
        for r in self._relationships:
            key = r.relation_type.value
            rel_counts[key] = rel_counts.get(key, 0) + 1
        return {
            "entities": len(self._entities),
            "relationships": len(self._relationships),
            "entity_types": type_counts,
            "relationship_types": rel_counts,
        }
