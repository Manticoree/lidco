"""Writing Improver — Suggest improvements for technical writing.

Simplify complex sentences, fix common grammar issues, add examples,
and improve structure.  Pure stdlib.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Suggestion:
    """A single improvement suggestion."""

    line: int
    category: str  # "simplify", "grammar", "structure", "example", "clarity"
    original: str
    replacement: str
    reason: str


@dataclass
class ImprovementResult:
    """Collection of improvement suggestions."""

    suggestions: list[Suggestion] = field(default_factory=list)
    simplified_text: str = ""
    original_word_count: int = 0
    simplified_word_count: int = 0

    @property
    def suggestion_count(self) -> int:
        return len(self.suggestions)


# ---------------------------------------------------------------------------
# Simplification rules: (pattern, replacement, reason)
# ---------------------------------------------------------------------------

_SIMPLIFY_RULES: list[tuple[str, str, str]] = [
    (r"\bin order to\b", "to", "Remove unnecessary words"),
    (r"\bdue to the fact that\b", "because", "Simplify phrasing"),
    (r"\bat this point in time\b", "now", "Remove verbosity"),
    (r"\bin the event that\b", "if", "Simplify conditional"),
    (r"\bfor the purpose of\b", "to", "Simplify phrasing"),
    (r"\bin the near future\b", "soon", "Remove verbosity"),
    (r"\ba large number of\b", "many", "Simplify quantity"),
    (r"\bin spite of the fact that\b", "although", "Simplify phrasing"),
    (r"\bhas the ability to\b", "can", "Simplify phrasing"),
    (r"\bit is important to note that\b", "", "Remove filler"),
    (r"\bit should be noted that\b", "", "Remove filler"),
    (r"\bplease note that\b", "", "Remove filler"),
    (r"\bas a matter of fact\b", "in fact", "Simplify phrasing"),
    (r"\bin the process of\b", "currently", "Simplify phrasing"),
    (r"\bwith regard to\b", "about", "Simplify phrasing"),
    (r"\bwith respect to\b", "about", "Simplify phrasing"),
    (r"\bat the present time\b", "now", "Remove verbosity"),
    (r"\bprior to\b", "before", "Simplify phrasing"),
    (r"\bsubsequent to\b", "after", "Simplify phrasing"),
    (r"\bin close proximity to\b", "near", "Remove verbosity"),
]

# ---------------------------------------------------------------------------
# Grammar patterns: (regex, replacement, reason)
# ---------------------------------------------------------------------------

_GRAMMAR_RULES: list[tuple[str, str, str]] = [
    (r"\bits\s+it's\b", "its", "Possessive 'its' does not need apostrophe"),
    (r"\btheir\s+is\b", "there is", "Wrong homophone"),
    (r"\byour\s+welcome\b", "you're welcome", "Wrong homophone"),
    (r"\bcould of\b", "could have", "Common grammar mistake"),
    (r"\bshould of\b", "should have", "Common grammar mistake"),
    (r"\bwould of\b", "would have", "Common grammar mistake"),
    (r"\balot\b", "a lot", "Should be two words"),
    (r"\bdefinately\b", "definitely", "Common misspelling"),
    (r"\boccured\b", "occurred", "Common misspelling"),
    (r"\brecieve\b", "receive", "Common misspelling"),
    (r"\bseperate\b", "separate", "Common misspelling"),
    (r"\bneccessary\b", "necessary", "Common misspelling"),
    (r"\baccommodate\b", "accommodate", "Verify spelling"),
]

# ---------------------------------------------------------------------------
# Structure checks
# ---------------------------------------------------------------------------

_MAX_SENTENCE_WORDS = 30
_MIN_PARAGRAPH_SENTENCES = 2

_WORD_RE = re.compile(r"[a-zA-Z']+")
_SENTENCE_RE = re.compile(r"[.!?]+(?:\s|$)")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text)
    return [s.strip() for s in parts if s.strip()]


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text))


# ---------------------------------------------------------------------------
# WritingImprover
# ---------------------------------------------------------------------------

class WritingImprover:
    """Suggest improvements for technical writing."""

    def __init__(
        self,
        *,
        simplify_rules: list[tuple[str, str, str]] | None = None,
        grammar_rules: list[tuple[str, str, str]] | None = None,
        max_sentence_words: int = _MAX_SENTENCE_WORDS,
    ) -> None:
        self._simplify_rules = simplify_rules or list(_SIMPLIFY_RULES)
        self._grammar_rules = grammar_rules or list(_GRAMMAR_RULES)
        self._max_sentence_words = max_sentence_words

    # -- public API ----------------------------------------------------------

    def improve(self, text: str) -> ImprovementResult:
        """Run all improvement checks and return suggestions + simplified text."""
        suggestions: list[Suggestion] = []
        suggestions.extend(self.simplify(text))
        suggestions.extend(self.fix_grammar(text))
        suggestions.extend(self.check_structure(text))

        simplified = self.apply_simplifications(text)

        return ImprovementResult(
            suggestions=suggestions,
            simplified_text=simplified,
            original_word_count=_word_count(text),
            simplified_word_count=_word_count(simplified),
        )

    def simplify(self, text: str) -> list[Suggestion]:
        """Suggest simplifications for complex/verbose phrases."""
        suggestions: list[Suggestion] = []
        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for pattern, replacement, reason in self._simplify_rules:
                for m in re.finditer(pattern, line, re.IGNORECASE):
                    suggestions.append(
                        Suggestion(
                            line=lineno,
                            category="simplify",
                            original=m.group(0),
                            replacement=replacement,
                            reason=reason,
                        )
                    )
        return suggestions

    def fix_grammar(self, text: str) -> list[Suggestion]:
        """Detect common grammar / spelling mistakes."""
        suggestions: list[Suggestion] = []
        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            for pattern, replacement, reason in self._grammar_rules:
                for m in re.finditer(pattern, line, re.IGNORECASE):
                    suggestions.append(
                        Suggestion(
                            line=lineno,
                            category="grammar",
                            original=m.group(0),
                            replacement=replacement,
                            reason=reason,
                        )
                    )
        return suggestions

    def check_structure(self, text: str) -> list[Suggestion]:
        """Check for overly long sentences and thin paragraphs."""
        suggestions: list[Suggestion] = []
        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            sentences = _split_sentences(line)
            for sentence in sentences:
                wc = _word_count(sentence)
                if wc > self._max_sentence_words:
                    suggestions.append(
                        Suggestion(
                            line=lineno,
                            category="structure",
                            original=sentence[:80] + ("..." if len(sentence) > 80 else ""),
                            replacement="(split into shorter sentences)",
                            reason=f"Sentence has {wc} words (max {self._max_sentence_words})",
                        )
                    )
        return suggestions

    def apply_simplifications(self, text: str) -> str:
        """Return *text* with all simplification rules applied."""
        result = text
        for pattern, replacement, _ in self._simplify_rules:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def suggest_examples(self, text: str) -> list[Suggestion]:
        """Suggest where examples could improve clarity."""
        suggestions: list[Suggestion] = []
        lines = text.splitlines()
        example_markers = {"for example", "e.g.", "such as", "for instance"}
        for lineno, line in enumerate(lines, start=1):
            lower = line.lower()
            has_example = any(marker in lower for marker in example_markers)
            # Flag technical assertions without examples
            if not has_example and _word_count(line) > 15:
                tech_words = {"api", "function", "method", "endpoint", "parameter", "module"}
                if any(w in lower for w in tech_words):
                    suggestions.append(
                        Suggestion(
                            line=lineno,
                            category="example",
                            original=line[:80] + ("..." if len(line) > 80 else ""),
                            replacement="(consider adding an example)",
                            reason="Technical statement without example",
                        )
                    )
        return suggestions
