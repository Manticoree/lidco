"""ConsistencyChecker — check response consistency and contradictions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Contradiction:
    """A detected contradiction."""

    statement_a: str
    statement_b: str
    explanation: str
    severity: str = "medium"  # "low", "medium", "high"


@dataclass
class ConsistencyResult:
    """Result of consistency check."""

    statements: int
    contradictions: list[Contradiction] = field(default_factory=list)
    is_consistent: bool = True
    confidence: float = 1.0


class ConsistencyChecker:
    """Check for contradictions within and across responses."""

    def __init__(self) -> None:
        self._prior_statements: list[str] = []
        self._results: list[ConsistencyResult] = []
        self._negation_pairs: list[tuple[str, str]] = [
            ("is not", "is"),
            ("cannot", "can"),
            ("should not", "should"),
            ("does not", "does"),
            ("will not", "will"),
            ("never", "always"),
            ("false", "true"),
            ("no", "yes"),
            ("impossible", "possible"),
            ("deprecated", "recommended"),
        ]

    def add_prior(self, statement: str) -> None:
        """Add a prior statement for cross-turn consistency checking."""
        self._prior_statements.append(statement)

    def check(self, statements: list[str]) -> ConsistencyResult:
        """Check a list of statements for internal consistency."""
        contradictions: list[Contradiction] = []

        # Check pairs within current statements
        for i in range(len(statements)):
            for j in range(i + 1, len(statements)):
                c = self._find_contradiction(statements[i], statements[j])
                if c:
                    contradictions.append(c)

        # Check against prior statements
        for stmt in statements:
            for prior in self._prior_statements:
                c = self._find_contradiction(stmt, prior)
                if c:
                    c.severity = "high"  # cross-turn contradictions are worse
                    contradictions.append(c)

        is_consistent = len(contradictions) == 0
        confidence = max(1.0 - len(contradictions) * 0.2, 0.0)

        result = ConsistencyResult(
            statements=len(statements),
            contradictions=contradictions,
            is_consistent=is_consistent,
            confidence=round(confidence, 3),
        )
        self._results.append(result)
        return result

    def _find_contradiction(self, a: str, b: str) -> Contradiction | None:
        """Heuristic contradiction detection between two statements."""
        a_lower = a.lower().strip()
        b_lower = b.lower().strip()

        for neg, pos in self._negation_pairs:
            # Check if one says "X is Y" and the other "X is not Y"
            if neg in a_lower and pos in b_lower:
                # Check if they share a subject (first few words)
                a_words = a_lower.split()[:3]
                b_words = b_lower.split()[:3]
                if set(a_words) & set(b_words):
                    return Contradiction(
                        statement_a=a,
                        statement_b=b,
                        explanation=f"Potential negation conflict: '{neg}' vs '{pos}'",
                    )
            if neg in b_lower and pos in a_lower:
                a_words = a_lower.split()[:3]
                b_words = b_lower.split()[:3]
                if set(a_words) & set(b_words):
                    return Contradiction(
                        statement_a=a,
                        statement_b=b,
                        explanation=f"Potential negation conflict: '{pos}' vs '{neg}'",
                    )
        return None

    def history(self) -> list[ConsistencyResult]:
        return list(self._results)

    def summary(self) -> dict:
        total_contradictions = sum(len(r.contradictions) for r in self._results)
        return {
            "checks": len(self._results),
            "total_contradictions": total_contradictions,
            "prior_statements": len(self._prior_statements),
        }
