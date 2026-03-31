"""Q137 — SimilarityMetrics: string similarity measures."""
from __future__ import annotations

import difflib
import math
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class SimilarityResult:
    """Result of a similarity comparison."""

    score: float
    method: str
    details: dict = field(default_factory=dict)


class SimilarityMetrics:
    """Collection of string similarity metrics (all static/classmethod)."""

    @staticmethod
    def levenshtein(a: str, b: str) -> int:
        """Compute Levenshtein edit distance between *a* and *b*."""
        if len(a) < len(b):
            return SimilarityMetrics.levenshtein(b, a)
        if len(b) == 0:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                insert = prev[j + 1] + 1
                delete = curr[j] + 1
                replace = prev[j] + (0 if ca == cb else 1)
                curr.append(min(insert, delete, replace))
            prev = curr
        return prev[-1]

    @staticmethod
    def ratio(a: str, b: str) -> float:
        """SequenceMatcher ratio between *a* and *b*."""
        return difflib.SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def jaccard(a: str, b: str) -> float:
        """Word-level Jaccard similarity."""
        set_a = set(a.split())
        set_b = set(b.split())
        if not set_a and not set_b:
            return 1.0
        intersection = set_a & set_b
        union = set_a | set_b
        if not union:
            return 1.0
        return len(intersection) / len(union)

    @staticmethod
    def cosine(a: str, b: str) -> float:
        """Word-frequency cosine similarity."""
        ca = Counter(a.split())
        cb = Counter(b.split())
        if not ca or not cb:
            return 0.0
        all_words = set(ca) | set(cb)
        dot = sum(ca.get(w, 0) * cb.get(w, 0) for w in all_words)
        mag_a = math.sqrt(sum(v * v for v in ca.values()))
        mag_b = math.sqrt(sum(v * v for v in cb.values()))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    @classmethod
    def compare(cls, a: str, b: str) -> dict:
        """Return all metrics in one call."""
        return {
            "levenshtein": cls.levenshtein(a, b),
            "ratio": cls.ratio(a, b),
            "jaccard": cls.jaccard(a, b),
            "cosine": cls.cosine(a, b),
        }
