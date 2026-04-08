"""Q329 — Knowledge Search: natural language search over the knowledge graph."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lidco.knowledge.graph import Entity, KnowledgeGraph, RelationType


@dataclass
class SearchHit:
    """A single search result with relevance score."""

    entity: Entity
    score: float
    context: str = ""
    related_entities: list[Entity] = field(default_factory=list)


@dataclass
class SearchResult:
    """Aggregated search results."""

    query: str
    hits: list[SearchHit] = field(default_factory=list)

    @property
    def hit_count(self) -> int:
        return len(self.hits)

    @property
    def top_hit(self) -> SearchHit | None:
        return self.hits[0] if self.hits else None

    def summary(self) -> str:
        if not self.hits:
            return f"No results for '{self.query}'."
        lines = [f"Found {self.hit_count} result(s) for '{self.query}':"]
        for hit in self.hits[:10]:
            lines.append(
                f"  [{hit.score:.2f}] {hit.entity.name} "
                f"({hit.entity.entity_type.value}) — {hit.entity.description}"
            )
        return "\n".join(lines)


# Stop words to ignore in natural language queries
_STOP_WORDS: set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "how", "does", "do",
    "what", "where", "when", "which", "who", "it", "its", "in", "on",
    "of", "to", "for", "with", "from", "by", "at", "and", "or", "not",
    "this", "that", "be", "have", "has", "had", "can", "could", "would",
    "should", "will", "work", "works", "working",
}


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, removing stop words."""
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS]


class KnowledgeSearch:
    """Natural language search over a KnowledgeGraph."""

    def __init__(self, graph: KnowledgeGraph) -> None:
        self._graph = graph

    def search(self, query: str, limit: int = 20) -> SearchResult:
        """Search entities by natural language query."""
        tokens = _tokenize(query)
        if not tokens:
            return SearchResult(query=query)

        scored: list[SearchHit] = []
        for entity in self._graph.all_entities():
            score = self._score_entity(entity, tokens)
            if score > 0.0:
                related = self._graph.neighbors(entity.id)[:5]
                context = self._build_context(entity, related)
                scored.append(
                    SearchHit(
                        entity=entity,
                        score=score,
                        context=context,
                        related_entities=related,
                    )
                )

        scored.sort(key=lambda h: h.score, reverse=True)
        return SearchResult(query=query, hits=scored[:limit])

    def answer(self, question: str) -> str:
        """Generate a simple text answer for a natural language question."""
        result = self.search(question, limit=5)
        if not result.hits:
            return f"I don't have information about '{question}' in the knowledge graph."

        top = result.hits[0]
        lines = [
            f"**{top.entity.name}** ({top.entity.entity_type.value})",
            "",
            top.entity.description or "(no description)",
        ]
        if top.entity.source_file:
            lines.append(f"Source: {top.entity.source_file}:{top.entity.line_number}")
        if top.related_entities:
            lines.append("")
            lines.append("Related:")
            for rel in top.related_entities[:5]:
                lines.append(f"  - {rel.name} ({rel.entity_type.value})")
        if len(result.hits) > 1:
            lines.append("")
            lines.append("See also:")
            for hit in result.hits[1:5]:
                lines.append(f"  - {hit.entity.name}: {hit.entity.description}")
        return "\n".join(lines)

    def find_by_concept(self, concept: str) -> SearchResult:
        """Search specifically for concept-type entities."""
        from lidco.knowledge.graph import EntityType

        tokens = _tokenize(concept)
        if not tokens:
            return SearchResult(query=concept)

        hits: list[SearchHit] = []
        for entity in self._graph.all_entities():
            if entity.entity_type not in (
                EntityType.CONCEPT,
                EntityType.PATTERN,
                EntityType.RULE,
            ):
                continue
            score = self._score_entity(entity, tokens)
            if score > 0.0:
                hits.append(SearchHit(entity=entity, score=score))

        hits.sort(key=lambda h: h.score, reverse=True)
        return SearchResult(query=concept, hits=hits[:20])

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_entity(self, entity: Entity, tokens: list[str]) -> float:
        """Score an entity against query tokens."""
        name_lower = entity.name.lower()
        desc_lower = entity.description.lower()
        tag_text = " ".join(entity.tags).lower()
        total = 0.0
        for token in tokens:
            if token == name_lower:
                total += 1.0
            elif token in name_lower:
                total += 0.6
            if token in desc_lower:
                total += 0.4
            if token in tag_text:
                total += 0.3
        # Normalize by token count
        return total / len(tokens) if tokens else 0.0

    def _build_context(self, entity: Entity, related: list[Entity]) -> str:
        """Build context string for a search hit."""
        parts = [entity.description]
        if entity.source_file:
            parts.append(f"Defined in {entity.source_file}")
        if related:
            rel_names = ", ".join(r.name for r in related[:3])
            parts.append(f"Related to: {rel_names}")
        return ". ".join(p for p in parts if p)
