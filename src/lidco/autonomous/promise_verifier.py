"""Promise verification and honesty checking (task 1054)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lidco.autonomous.loop_config import IterationResult


@dataclass(frozen=True)
class VerificationResult:
    """Immutable result of promise verification."""

    verified: bool
    confidence: float
    evidence: str


@dataclass(frozen=True)
class HonestyReport:
    """Immutable honesty assessment of an iteration history."""

    honest: bool
    flags: tuple[str, ...]
    recommendation: str


# Patterns that suggest a completion claim
_COMPLETION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bcomplete[d]?\b", re.IGNORECASE),
    re.compile(r"\bfinished\b", re.IGNORECASE),
    re.compile(r"\bdone\b", re.IGNORECASE),
    re.compile(r"\ball (?:tasks?|steps?|items?) (?:are )?(?:complete|done|finished)\b", re.IGNORECASE),
    re.compile(r"\bsuccessfully\b", re.IGNORECASE),
    re.compile(r"\bno (?:more |remaining )?(?:issues?|errors?|failures?)\b", re.IGNORECASE),
)


class PromiseVerifier:
    """Verify completion promises and assess honesty of iteration histories."""

    def verify(self, output: str, promise: str) -> VerificationResult:
        """Check whether *output* genuinely satisfies *promise*.

        Does more than a simple substring check: looks for the promise text
        AND supporting evidence (completion-like language).
        """
        promise_lower = promise.lower()
        output_lower = output.lower()

        # Basic check: promise text present?
        text_present = promise_lower in output_lower

        if not text_present:
            return VerificationResult(
                verified=False,
                confidence=0.0,
                evidence="Promise text not found in output.",
            )

        # Look for supporting completion language
        support_count = sum(
            1 for pat in _COMPLETION_PATTERNS if pat.search(output)
        )
        confidence = min(1.0, 0.4 + support_count * 0.15)

        # Penalise if the output also contains error / failure language
        error_patterns = (
            re.compile(r"\bERROR\b"),
            re.compile(r"\bfailed\b", re.IGNORECASE),
            re.compile(r"\bexception\b", re.IGNORECASE),
            re.compile(r"\btraceback\b", re.IGNORECASE),
        )
        error_count = sum(1 for p in error_patterns if p.search(output))
        if error_count:
            confidence = max(0.0, confidence - error_count * 0.2)

        verified = confidence >= 0.5
        evidence = (
            f"Promise text present. {support_count} completion signal(s), "
            f"{error_count} error signal(s). Confidence: {confidence:.2f}."
        )
        return VerificationResult(
            verified=verified,
            confidence=confidence,
            evidence=evidence,
        )

    def extract_claims(self, output: str) -> list[str]:
        """Extract sentences that look like completion claims."""
        sentences = re.split(r"[.!?\n]+", output)
        claims: list[str] = []
        for sentence in sentences:
            stripped = sentence.strip()
            if not stripped:
                continue
            for pat in _COMPLETION_PATTERNS:
                if pat.search(stripped):
                    claims.append(stripped)
                    break
        return claims

    def check_honesty(self, iterations: list[IterationResult]) -> HonestyReport:
        """Detect dishonest patterns in iteration history.

        Flags:
        - ``premature_claim``: claimed complete on first iteration
        - ``flip_flop``: alternated between claiming and not-claiming
        - ``stuck_loop``: repeated near-identical outputs
        - ``persistent_error``: errors in the majority of iterations
        """
        flags: list[str] = []

        if not iterations:
            return HonestyReport(
                honest=True,
                flags=(),
                recommendation="No iterations to assess.",
            )

        # Premature claim
        if len(iterations) >= 1 and iterations[0].claimed_complete:
            flags.append("premature_claim")

        # Flip-flop detection
        claims = [it.claimed_complete for it in iterations]
        flips = sum(
            1 for a, b in zip(claims, claims[1:]) if a != b
        )
        if flips >= 3:
            flags.append("flip_flop")

        # Stuck loop (3+ consecutive near-identical outputs)
        for i in range(len(iterations) - 2):
            a = iterations[i].output.strip()
            b = iterations[i + 1].output.strip()
            c = iterations[i + 2].output.strip()
            if a and a == b == c:
                flags.append("stuck_loop")
                break

        # Persistent errors
        error_count = sum(
            1 for it in iterations if it.output.startswith("ERROR:")
        )
        if len(iterations) >= 3 and error_count > len(iterations) // 2:
            flags.append("persistent_error")

        honest = len(flags) == 0
        if not flags:
            recommendation = "Iteration history looks clean."
        elif "stuck_loop" in flags:
            recommendation = "Loop appears stuck. Consider changing the prompt or aborting."
        elif "flip_flop" in flags:
            recommendation = "Agent is flip-flopping on completion. Verify manually."
        elif "premature_claim" in flags:
            recommendation = "Completion claimed on first iteration. Verify output carefully."
        else:
            recommendation = "Errors detected in most iterations. Investigate root cause."

        return HonestyReport(
            honest=honest,
            flags=tuple(flags),
            recommendation=recommendation,
        )


__all__ = [
    "HonestyReport",
    "PromiseVerifier",
    "VerificationResult",
]
