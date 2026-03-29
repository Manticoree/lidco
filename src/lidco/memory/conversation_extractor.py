"""ConversationMemoryExtractor -- extract reusable facts from conversation transcripts."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ExtractedFact:
    """A single fact extracted from a conversation."""

    content: str
    confidence: float  # 0.0-1.0
    tags: list[str] = field(default_factory=list)
    source_turn: int = 0

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "confidence": self.confidence,
            "tags": list(self.tags),
            "source_turn": self.source_turn,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExtractedFact:
        return cls(
            content=d["content"],
            confidence=d["confidence"],
            tags=d.get("tags", []),
            source_turn=d.get("source_turn", 0),
        )


# Heuristic patterns for fact extraction (compiled once)
_PREFERENCE_PATTERNS = [
    re.compile(r"(?:i |we )prefer\b.+", re.IGNORECASE),
    re.compile(r"always use\b.+", re.IGNORECASE),
    re.compile(r"never use\b.+", re.IGNORECASE),
    re.compile(r"project uses?\b.+", re.IGNORECASE),
    re.compile(r"we use\b.+", re.IGNORECASE),
]

_IDENTITY_PATTERNS = [
    re.compile(r"i am\b.+", re.IGNORECASE),
    re.compile(r"i'm a\b.+", re.IGNORECASE),
]

# Keywords to extract tags from
_TAG_KEYWORDS = {
    "python", "javascript", "typescript", "react", "django", "flask",
    "rust", "go", "java", "docker", "kubernetes", "aws", "git",
    "testing", "tdd", "ci", "cd", "api", "database", "sql",
    "frontend", "backend", "devops", "security", "performance",
}


def _extract_tags(text: str) -> list[str]:
    """Extract tag keywords from text."""
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return sorted(words & _TAG_KEYWORDS)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


class ConversationMemoryExtractor:
    """Extract reusable facts from conversation transcripts."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def extract(
        self,
        transcript: list[dict],
        llm_fn=None,
    ) -> list[ExtractedFact]:
        """Parse conversation transcript for declarative reusable facts.

        transcript: list of {"role": str, "content": str} dicts.
        llm_fn: optional callable (prompt: str) -> str for LLM-based extraction.
        Returns deduplicated ExtractedFact list.
        """
        if not transcript:
            return []

        if llm_fn is not None:
            return self._extract_with_llm(transcript, llm_fn)

        return self._extract_with_heuristics(transcript)

    def _extract_with_llm(
        self,
        transcript: list[dict],
        llm_fn,
    ) -> list[ExtractedFact]:
        """Use LLM to extract facts from transcript."""
        text_parts = []
        for turn in transcript:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            if content:
                text_parts.append(f"{role}: {content}")

        combined = "\n".join(text_parts)
        prompt = (
            "Extract reusable declarative facts from this conversation. "
            "Return one fact per line. Only include preferences, conventions, "
            "and project details that would be useful to remember.\n\n"
            f"{combined}"
        )

        try:
            response = llm_fn(prompt)
        except Exception:
            return self._extract_with_heuristics(transcript)

        facts: list[ExtractedFact] = []
        self._seen.clear()

        for line in response.strip().splitlines():
            line = line.strip().lstrip("- ").strip()
            if not line or len(line) < 5:
                continue
            key = line.lower()
            if key in self._seen:
                continue
            self._seen.add(key)
            facts.append(ExtractedFact(
                content=line,
                confidence=0.85,
                tags=_extract_tags(line),
                source_turn=0,
            ))

        return facts

    def _extract_with_heuristics(
        self,
        transcript: list[dict],
    ) -> list[ExtractedFact]:
        """Use regex heuristics to extract facts."""
        facts: list[ExtractedFact] = []
        self._seen.clear()

        for turn_idx, turn in enumerate(transcript):
            content = turn.get("content", "")
            if not content or not isinstance(content, str):
                continue

            role = turn.get("role", "")
            if role not in ("user", "assistant", "human"):
                continue

            sentences = _split_sentences(content)
            for sentence in sentences:
                fact = self._match_sentence(sentence, turn_idx)
                if fact is not None:
                    key = fact.content.lower()
                    if key not in self._seen:
                        self._seen.add(key)
                        facts.append(fact)

        return facts

    def _match_sentence(self, sentence: str, turn_idx: int) -> ExtractedFact | None:
        """Try to match a sentence against known patterns."""
        stripped = sentence.strip()
        if len(stripped) < 5:
            return None

        # Check preference patterns (confidence 0.7)
        for pattern in _PREFERENCE_PATTERNS:
            match = pattern.search(stripped)
            if match:
                return ExtractedFact(
                    content=stripped,
                    confidence=0.7,
                    tags=_extract_tags(stripped),
                    source_turn=turn_idx,
                )

        # Check identity patterns (confidence 0.6)
        for pattern in _IDENTITY_PATTERNS:
            match = pattern.search(stripped)
            if match:
                return ExtractedFact(
                    content=stripped,
                    confidence=0.6,
                    tags=_extract_tags(stripped),
                    source_turn=turn_idx,
                )

        return None

    def extract_high_confidence(
        self,
        transcript: list[dict],
        threshold: float = 0.8,
        llm_fn=None,
    ) -> list[ExtractedFact]:
        """Extract only high-confidence facts (auto-promote candidates)."""
        all_facts = self.extract(transcript, llm_fn=llm_fn)
        return [f for f in all_facts if f.confidence > threshold]
