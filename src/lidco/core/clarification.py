"""Clarification system for handling ambiguous requests."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from lidco.core.memory import MemoryEntry, MemoryStore
from lidco.llm.base import BaseLLMProvider, Message

logger = logging.getLogger(__name__)

_DECISION_KEY_LIMIT = 100_000


@dataclass(frozen=True)
class ClarificationNeeded(Exception):
    """Raised by ask_user tool to pause execution and ask the user a question."""

    question: str
    options: list[str]
    context: str

    def __str__(self) -> str:
        return self.question


@dataclass(frozen=True)
class ClarificationEntry:
    """A saved clarification decision."""

    question: str
    answer: str
    context: str
    agent: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "context": self.context,
            "agent": self.agent,
            "timestamp": self.timestamp,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ClarificationEntry:
        return ClarificationEntry(
            question=data["question"],
            answer=data["answer"],
            context=data.get("context", ""),
            agent=data.get("agent", ""),
            timestamp=data.get("timestamp", ""),
        )


AMBIGUITY_ANALYSIS_PROMPT = """\
Analyze user request for ambiguity. Return JSON:
Clear: {{"clear": true}}
Ambiguous: {{"clear": false, "questions": [{{"question": "...", "options": [...], "context": "why"}}]}}

Max 3 questions. Only genuinely ambiguous requests. Concrete options.

User message:
{user_message}
"""


class ClarificationManager:
    """Manages clarification questions, decisions, and ambiguity analysis."""

    def __init__(self, memory: MemoryStore) -> None:
        self._memory = memory

    def save_decision(
        self,
        question: str,
        answer: str,
        context: str = "",
        agent: str = "",
    ) -> None:
        """Save a clarification decision to memory."""
        if not question or not answer:
            return

        key = f"decision_{abs(hash(question)) % _DECISION_KEY_LIMIT}"

        # Store structured JSON so parsing is reliable
        structured = json.dumps({
            "question": question,
            "answer": answer,
            "context": context,
            "agent": agent,
        }, ensure_ascii=False)

        self._memory.add(
            key=key,
            content=structured,
            category="decision",
            tags=["clarification", agent] if agent else ["clarification"],
            source="clarification",
        )

    @staticmethod
    def _parse_memory_entry(mem: MemoryEntry) -> ClarificationEntry | None:
        """Parse a MemoryEntry into a ClarificationEntry."""
        try:
            data = json.loads(mem.content)
            return ClarificationEntry(
                question=data["question"],
                answer=data["answer"],
                context=data.get("context", ""),
                agent=data.get("agent", ""),
                timestamp=mem.created_at,
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def find_relevant(self, query: str, limit: int = 5) -> list[ClarificationEntry]:
        """Find relevant past decisions."""
        results = self._memory.search(query, category="decision", limit=limit)
        return [
            entry
            for mem in results
            if (entry := self._parse_memory_entry(mem)) is not None
        ]

    def list_recent(self, n: int = 20) -> list[ClarificationEntry]:
        """List recent decisions."""
        all_decisions = self._memory.list_all(category="decision")
        entries: list[ClarificationEntry] = []
        for mem in all_decisions[-n:]:
            entry = self._parse_memory_entry(mem)
            if entry is not None:
                entries.append(entry)
        return entries

    def build_context_string(self) -> str:
        """Build decisions context string for system prompts."""
        entries = self.list_recent(5)
        if not entries:
            return ""
        lines = ["## Past Decisions"]
        for entry in entries:
            lines.append(f"- **{entry.question}**: {entry.answer}")
        return "\n".join(lines)

    def clear(self) -> int:
        """Clear all decision entries. Returns count of removed entries."""
        all_decisions = self._memory.list_all(category="decision")
        count = 0
        for entry in all_decisions:
            if self._memory.remove(entry.key):
                count += 1
        return count

    async def analyze_ambiguity(
        self,
        user_message: str,
        llm: BaseLLMProvider,
    ) -> list[ClarificationNeeded] | None:
        """Analyze a user message for ambiguity using a lightweight LLM call.

        Returns None if the request is clear or if analysis fails (fail-open).
        """
        # Skip analysis for short, obviously clear messages
        stripped = user_message.strip()
        if len(stripped) < 40 and "?" not in stripped:
            return None

        prompt = AMBIGUITY_ANALYSIS_PROMPT.format(user_message=user_message)

        try:
            response = await llm.complete(
                [
                    Message(role="system", content=prompt),
                ],
                temperature=0.0,
                max_tokens=200,
                role="routing",
            )

            raw = response.content.strip()
            json_str = raw
            if "```" in json_str:
                json_str = json_str.split("```")[1].lstrip("json\n")
            if "{" in json_str:
                json_str = json_str[json_str.index("{"):json_str.rindex("}") + 1]
            else:
                return None

            result = json.loads(json_str)

            if result.get("clear", True):
                return None

            questions = result.get("questions", [])
            if not questions:
                return None

            return [
                ClarificationNeeded(
                    question=q["question"],
                    options=q.get("options", []),
                    context=q.get("context", ""),
                )
                for q in questions
            ]
        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
            logger.warning("Ambiguity analysis parse failed, assuming clear: %s", e)
            return None
        except Exception as e:
            logger.warning("Ambiguity analysis failed, assuming clear: %s", e)
            return None
