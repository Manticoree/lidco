"""Writing Analyzer — Analyze technical writing quality.

Provides readability scoring, jargon detection, consistency checks,
and tone analysis.  Pure stdlib, no external dependencies.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReadabilityScore:
    """Flesch-Kincaid style readability result."""

    grade_level: float
    reading_ease: float
    avg_sentence_length: float
    avg_syllables_per_word: float

    @property
    def label(self) -> str:
        if self.reading_ease >= 80:
            return "easy"
        if self.reading_ease >= 60:
            return "standard"
        if self.reading_ease >= 40:
            return "moderate"
        return "difficult"


@dataclass(frozen=True)
class JargonMatch:
    """A single jargon detection hit."""

    term: str
    line: int
    suggestion: str


@dataclass(frozen=True)
class ConsistencyIssue:
    """Inconsistent usage of a term/spelling."""

    term: str
    variant: str
    occurrences: int
    preferred: str


@dataclass(frozen=True)
class ToneResult:
    """Tone analysis summary."""

    formality: float  # 0.0 (informal) .. 1.0 (formal)
    confidence: float  # 0.0 (hedging) .. 1.0 (assertive)
    label: str  # e.g. "formal", "neutral", "informal"


@dataclass
class AnalysisResult:
    """Full analysis result combining all checks."""

    readability: ReadabilityScore
    jargon: list[JargonMatch] = field(default_factory=list)
    consistency_issues: list[ConsistencyIssue] = field(default_factory=list)
    tone: ToneResult = field(default_factory=lambda: ToneResult(0.5, 0.5, "neutral"))
    word_count: int = 0
    sentence_count: int = 0


# ---------------------------------------------------------------------------
# Built-in jargon dictionary (term -> suggestion)
# ---------------------------------------------------------------------------

DEFAULT_JARGON: dict[str, str] = {
    "leverage": "use",
    "utilize": "use",
    "utilise": "use",
    "paradigm": "approach",
    "synergy": "collaboration",
    "actionable": "practical",
    "bandwidth": "capacity (if not networking)",
    "circle back": "follow up",
    "deep dive": "detailed look",
    "low-hanging fruit": "easy win",
    "boil the ocean": "over-scope",
    "move the needle": "make progress",
    "touch base": "check in",
    "net-net": "summary",
    "bleeding edge": "latest",
    "best-of-breed": "best available",
    "robust": "strong (be specific)",
    "scalable": "(be specific about scaling dimension)",
    "performant": "fast (be specific)",
}

# ---------------------------------------------------------------------------
# Consistency pairs: (variant_a, variant_b, preferred)
# ---------------------------------------------------------------------------

CONSISTENCY_PAIRS: list[tuple[str, str, str]] = [
    ("e-mail", "email", "email"),
    ("frontend", "front-end", "frontend"),
    ("backend", "back-end", "backend"),
    ("color", "colour", "color"),
    ("gray", "grey", "gray"),
    ("canceled", "cancelled", "canceled"),
    ("login", "log-in", "login"),
    ("setup", "set-up", "setup"),
    ("ok", "okay", "okay"),
    ("database", "data base", "database"),
    ("filename", "file name", "filename"),
    ("username", "user name", "username"),
    ("config", "configuration", "configuration"),
    ("repo", "repository", "repository"),
    ("info", "information", "information"),
]

# ---------------------------------------------------------------------------
# Informal / hedging markers for tone analysis
# ---------------------------------------------------------------------------

_INFORMAL_MARKERS = {
    "gonna", "wanna", "kinda", "sorta", "gotta", "y'all",
    "stuff", "things", "cool", "awesome", "basically",
    "actually", "literally", "like", "just", "really",
}

_HEDGE_MARKERS = {
    "maybe", "perhaps", "possibly", "might", "could",
    "seems", "appears", "somewhat", "arguably", "presumably",
    "likely", "unlikely", "probably", "sort of", "kind of",
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

_SENTENCE_RE = re.compile(r"[.!?]+(?:\s|$)")
_WORD_RE = re.compile(r"[a-zA-Z']+")

# Rough syllable counter (English approximation)
_VOWEL_GROUP = re.compile(r"[aeiouy]+", re.IGNORECASE)


def _count_syllables(word: str) -> int:
    """Approximate syllable count for an English word."""
    word = word.lower().rstrip("e")
    groups = _VOWEL_GROUP.findall(word)
    count = len(groups)
    return max(count, 1)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences (simple heuristic)."""
    parts = _SENTENCE_RE.split(text)
    return [s.strip() for s in parts if s.strip()]


def _get_words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


# ---------------------------------------------------------------------------
# WritingAnalyzer
# ---------------------------------------------------------------------------

class WritingAnalyzer:
    """Analyze technical writing quality."""

    def __init__(
        self,
        *,
        jargon_dict: dict[str, str] | None = None,
        consistency_pairs: list[tuple[str, str, str]] | None = None,
    ) -> None:
        self._jargon = jargon_dict if jargon_dict is not None else dict(DEFAULT_JARGON)
        self._consistency = (
            consistency_pairs if consistency_pairs is not None else list(CONSISTENCY_PAIRS)
        )

    # -- public API ----------------------------------------------------------

    def analyze(self, text: str) -> AnalysisResult:
        """Run full analysis on *text* and return an :class:`AnalysisResult`."""
        readability = self.readability(text)
        jargon = self.detect_jargon(text)
        consistency = self.check_consistency(text)
        tone = self.analyze_tone(text)
        words = _get_words(text)
        sentences = _split_sentences(text)
        return AnalysisResult(
            readability=readability,
            jargon=jargon,
            consistency_issues=consistency,
            tone=tone,
            word_count=len(words),
            sentence_count=len(sentences),
        )

    def readability(self, text: str) -> ReadabilityScore:
        """Compute Flesch-Kincaid readability metrics."""
        sentences = _split_sentences(text)
        words = _get_words(text)
        if not words or not sentences:
            return ReadabilityScore(
                grade_level=0.0,
                reading_ease=100.0,
                avg_sentence_length=0.0,
                avg_syllables_per_word=0.0,
            )
        total_syllables = sum(_count_syllables(w) for w in words)
        avg_sl = len(words) / len(sentences)
        avg_syl = total_syllables / len(words)

        reading_ease = 206.835 - 1.015 * avg_sl - 84.6 * avg_syl
        grade_level = 0.39 * avg_sl + 11.8 * avg_syl - 15.59

        return ReadabilityScore(
            grade_level=round(max(grade_level, 0.0), 2),
            reading_ease=round(max(min(reading_ease, 100.0), 0.0), 2),
            avg_sentence_length=round(avg_sl, 2),
            avg_syllables_per_word=round(avg_syl, 2),
        )

    def detect_jargon(self, text: str) -> list[JargonMatch]:
        """Find jargon terms in *text*."""
        matches: list[JargonMatch] = []
        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            lower = line.lower()
            for term, suggestion in self._jargon.items():
                if term.lower() in lower:
                    matches.append(JargonMatch(term=term, line=lineno, suggestion=suggestion))
        return matches

    def check_consistency(self, text: str) -> list[ConsistencyIssue]:
        """Check for inconsistent term usage."""
        issues: list[ConsistencyIssue] = []
        lower = text.lower()
        for var_a, var_b, preferred in self._consistency:
            count_a = lower.count(var_a.lower())
            count_b = lower.count(var_b.lower())
            if count_a > 0 and count_b > 0:
                # Both variants present — flag the non-preferred
                non_preferred = var_a if preferred.lower() == var_b.lower() else var_b
                non_count = count_a if non_preferred == var_a else count_b
                issues.append(
                    ConsistencyIssue(
                        term=preferred,
                        variant=non_preferred,
                        occurrences=non_count,
                        preferred=preferred,
                    )
                )
        return issues

    def analyze_tone(self, text: str) -> ToneResult:
        """Analyze formality and confidence of writing."""
        words = [w.lower() for w in _get_words(text)]
        if not words:
            return ToneResult(formality=0.5, confidence=0.5, label="neutral")

        informal_count = sum(1 for w in words if w in _INFORMAL_MARKERS)
        hedge_count = sum(1 for w in words if w in _HEDGE_MARKERS)
        total = len(words)

        informality_ratio = informal_count / total
        hedge_ratio = hedge_count / total

        formality = round(max(0.0, min(1.0, 1.0 - informality_ratio * 10)), 2)
        confidence = round(max(0.0, min(1.0, 1.0 - hedge_ratio * 10)), 2)

        if formality >= 0.7:
            label = "formal"
        elif formality >= 0.4:
            label = "neutral"
        else:
            label = "informal"

        return ToneResult(formality=formality, confidence=confidence, label=label)
