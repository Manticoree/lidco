"""Natural language to structured code query."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lidco.understanding.semantic_search import SemanticSearchIndex


@dataclass(frozen=True)
class CodeQueryResult:
    """Result of a code query."""

    matches: tuple[dict[str, Any], ...] = ()
    query: str = ""
    total: int = 0


class CodeQueryEngine:
    """Translate natural language queries into structured code searches."""

    def __init__(self, search_index: SemanticSearchIndex | None = None) -> None:
        self._index = search_index or SemanticSearchIndex()
        self._history: list[str] = []

    def query(self, nl_query: str) -> CodeQueryResult:
        """Parse *nl_query*, search the index, return results."""
        self._history.append(nl_query)
        parsed = self.parse_query(nl_query)
        results = self._index.search(nl_query, top_k=parsed.get("limit", 10))
        matches = tuple(
            {
                "path": r.path,
                "name": r.name,
                "score": r.score,
                "snippet": r.snippet,
                "scope": r.scope.value,
            }
            for r in results
        )
        return CodeQueryResult(
            matches=matches,
            query=nl_query,
            total=len(matches),
        )

    def parse_query(self, nl_query: str) -> dict[str, Any]:
        """Extract structured fields from a natural language query."""
        words = nl_query.lower().split()
        kind: str = "any"
        name_pattern: str = ""
        limit: int = 10

        kind_keywords = {
            "function": "function",
            "func": "function",
            "method": "method",
            "class": "class",
            "variable": "variable",
            "var": "variable",
            "file": "file",
            "module": "module",
        }
        for w in words:
            cleaned = w.strip("?.,!:;")
            if cleaned in kind_keywords:
                kind = kind_keywords[cleaned]
                break

        # Look for quoted name patterns
        quoted = re.findall(r'"([^"]+)"', nl_query)
        if quoted:
            name_pattern = quoted[0]
        else:
            # Look for CamelCase or snake_case tokens
            for w in words:
                cleaned = w.strip("?.,!:;")
                if "_" in cleaned or (
                    len(cleaned) > 2 and any(c.isupper() for c in cleaned[1:])
                ):
                    name_pattern = cleaned
                    break

        return {
            "kind": kind,
            "name_pattern": name_pattern,
            "limit": limit,
            "raw": nl_query,
        }

    def explain(self, nl_query: str) -> str:
        """Human-readable explanation of how the query was interpreted."""
        parsed = self.parse_query(nl_query)
        parts: list[str] = [f"Query: {nl_query}"]
        parts.append(f"  Target kind: {parsed['kind']}")
        if parsed["name_pattern"]:
            parts.append(f"  Name pattern: {parsed['name_pattern']}")
        parts.append(f"  Max results: {parsed['limit']}")
        return "\n".join(parts)

    def history(self) -> list[str]:
        """Return past queries."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear query history."""
        self._history.clear()
