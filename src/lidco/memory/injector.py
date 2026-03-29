"""MemoryInjector -- compose approved memories into system prompt blocks."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class InjectionResult:
    """Result of memory injection composition."""

    prompt_block: str
    facts_included: int
    facts_dropped: int
    tokens_used: int  # rough estimate: len(prompt_block) // 4


class MemoryInjector:
    """Compose approved memories into a system prompt block."""

    def __init__(self, memory_store=None, session_seeder=None) -> None:
        self._memory_store = memory_store
        self._session_seeder = session_seeder

    def compose(self, query: str = "", budget: int = 2048) -> InjectionResult:
        """Build a system prompt block from approved memories.

        Filter by relevance to query (simple keyword overlap if no LLM).
        Drop lowest-relevance facts first when over budget.
        """
        facts = self._gather_facts()
        if not facts:
            return InjectionResult(
                prompt_block="",
                facts_included=0,
                facts_dropped=0,
                tokens_used=0,
            )

        # Score facts by relevance
        scored = self._score_facts(facts, query)

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Build prompt block within budget
        char_budget = budget * 4  # rough token-to-char ratio
        header = "## Remembered Context\n\n"
        lines: list[str] = [header]
        used_chars = len(header)
        included = 0
        dropped = 0

        for _score, fact_text in scored:
            line = f"- {fact_text}\n"
            if used_chars + len(line) > char_budget:
                dropped += 1
                continue
            lines.append(line)
            used_chars += len(line)
            included += 1

        prompt_block = "".join(lines) if included > 0 else ""
        return InjectionResult(
            prompt_block=prompt_block,
            facts_included=included,
            facts_dropped=dropped,
            tokens_used=len(prompt_block) // 4,
        )

    def inject_into_prompt(
        self,
        base_prompt: str,
        query: str = "",
        budget: int = 2048,
    ) -> str:
        """Prepend memory block to base_prompt."""
        result = self.compose(query=query, budget=budget)
        if not result.prompt_block:
            return base_prompt
        return result.prompt_block + "\n" + base_prompt

    def _gather_facts(self) -> list[str]:
        """Gather fact strings from memory_store and session_seeder."""
        facts: list[str] = []

        # Try memory_store
        if self._memory_store is not None:
            try:
                memories = self._memory_store.list(limit=50)
                for m in memories:
                    content = getattr(m, "content", None)
                    if content is None and isinstance(m, dict):
                        content = m.get("content", "")
                    if content:
                        facts.append(str(content))
            except Exception:
                pass

        # Try session_seeder
        if self._session_seeder is not None:
            try:
                ctx = self._session_seeder.seed()
                memories = getattr(ctx, "memories", [])
                for m in memories:
                    content = getattr(m, "content", None)
                    if content is None and isinstance(m, dict):
                        content = m.get("content", "")
                    if content and str(content) not in facts:
                        facts.append(str(content))
            except Exception:
                pass

        return facts

    def _score_facts(
        self,
        facts: list[str],
        query: str,
    ) -> list[tuple[float, str]]:
        """Score facts by keyword overlap with query."""
        if not query.strip():
            # No query: all facts get equal score, preserve order
            return [(1.0, f) for f in facts]

        query_words = set(re.findall(r"\b\w+\b", query.lower()))
        scored: list[tuple[float, str]] = []
        for fact in facts:
            fact_words = set(re.findall(r"\b\w+\b", fact.lower()))
            if not query_words:
                score = 1.0
            else:
                overlap = len(query_words & fact_words)
                score = overlap / len(query_words)
            scored.append((score, fact))
        return scored
