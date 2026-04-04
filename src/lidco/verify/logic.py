"""LogicVerifier — verify logical consistency of statement chains.

Stdlib only, dataclass results.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LogicResult:
    """Result of a logic verification pass."""

    is_valid: bool
    issues: list[str] = field(default_factory=list)


class LogicVerifier:
    """Verify logical consistency of reasoning chains."""

    # ------------------------------------------------------------------
    # check_circular
    # ------------------------------------------------------------------
    def check_circular(self, statements: list[str]) -> list[str]:
        """Return list of circular-reference issues.

        A circular reference is detected when a later statement is
        textually contained in an earlier one *and* vice-versa, or when
        the same statement appears more than once.
        """
        issues: list[str] = []
        seen: dict[str, int] = {}
        for idx, stmt in enumerate(statements):
            normalised = stmt.strip().lower()
            if normalised in seen:
                issues.append(
                    f"Circular: statement {idx} duplicates statement {seen[normalised]}"
                )
            else:
                seen[normalised] = idx
        return issues

    # ------------------------------------------------------------------
    # check_syllogism
    # ------------------------------------------------------------------
    def check_syllogism(
        self, premise1: str, premise2: str, conclusion: str
    ) -> bool:
        """Return True when *conclusion* plausibly follows from premises.

        Heuristic: every significant word (len>=3) in the conclusion
        must appear in at least one premise.
        """
        p1_words = set(premise1.lower().split())
        p2_words = set(premise2.lower().split())
        combined = p1_words | p2_words
        for word in conclusion.lower().split():
            if len(word) >= 3 and word not in combined:
                return False
        return True

    # ------------------------------------------------------------------
    # find_gaps
    # ------------------------------------------------------------------
    def find_gaps(self, chain: list[str]) -> list[str]:
        """Return gaps where consecutive statements share no vocabulary.

        A gap is reported between statement *i* and *i+1* when they
        share no significant word (len>=3).
        """
        gaps: list[str] = []
        for i in range(len(chain) - 1):
            words_a = {w for w in chain[i].lower().split() if len(w) >= 3}
            words_b = {w for w in chain[i + 1].lower().split() if len(w) >= 3}
            if not words_a & words_b:
                gaps.append(
                    f"Gap between statement {i} and {i + 1}: "
                    f"no shared vocabulary"
                )
        return gaps

    # ------------------------------------------------------------------
    # verify
    # ------------------------------------------------------------------
    def verify(self, statements: list[str]) -> LogicResult:
        """Run all checks and return a combined LogicResult."""
        issues: list[str] = []
        issues.extend(self.check_circular(statements))
        issues.extend(self.find_gaps(statements))
        return LogicResult(is_valid=len(issues) == 0, issues=issues)
