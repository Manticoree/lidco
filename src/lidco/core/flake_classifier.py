"""Flake root-cause classifier — categorises flaky tests by failure pattern.

Four categories are recognised:

* ``TIMING``   — test fails due to time-dependent behaviour (timeouts, slow I/O).
* ``ORDERING`` — test fails when run after/before a specific other test (shared
                  state, fixture setup/teardown issues).
* ``RESOURCE`` — test fails due to external resource unavailability (ports, files,
                  disk space, permissions).
* ``RANDOM``   — test fails non-deterministically due to random seeds, hash
                  randomisation, or UUID generation.
* ``UNKNOWN``  — no pattern matched.

Usage::

    from lidco.core.flake_classifier import classify_flake, classify_many

    clf = classify_flake(flake_record, outcomes)
    print(clf.category.value, clf.reason)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from lidco.core.flake_detector import FlakeRecord, TestOutcome


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class FlakeCategory(Enum):
    """Root-cause category for a flaky test."""

    TIMING = "timing"
    ORDERING = "ordering"
    RESOURCE = "resource"
    RANDOM = "random"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FlakeClassification:
    """Classification result for a single flaky test.

    Attributes:
        test_id:    Test identifier.
        category:   Detected root-cause :class:`FlakeCategory`.
        confidence: Heuristic confidence score in ``[0, 1]``.
        reason:     Short human-readable explanation.
    """

    test_id: str
    category: FlakeCategory
    confidence: float
    reason: str


# ---------------------------------------------------------------------------
# Pattern tables
# ---------------------------------------------------------------------------

_TIMING_PATTERNS: tuple[str, ...] = (
    "timeout",
    "timed out",
    "deadlineexceeded",
    "deadline exceeded",
    "took too long",
    "elapsed",
    "within 2s",
    "within 5s",
    "within 10s",
    "asyncio.timeouterror",
    "waitfortimeout",
    "readtimeouterror",
    "connectiontimeout",
)

_ORDERING_PATTERNS: tuple[str, ...] = (
    "fixture",
    "at setup of",
    "at teardown of",
    "setup failed",
    "teardown failed",
    "error in setup",
    "error in teardown",
    "test order",
    "depends on",
    "already closed",
    "connection was closed",
)

_RESOURCE_PATTERNS: tuple[str, ...] = (
    "address already in use",
    "errno 98",
    "errno 48",  # macOS EADDRINUSE
    "filenotfounderror",
    "no such file or directory",
    "permissionerror",
    "permission denied",
    "errno 13",
    "no space left",
    "errno 28",
    "disk quota",
    "connectionrefused",
    "connection refused",
    "temporaryfileerror",
    "oserror",
    "ioerror",
)

_RANDOM_PATTERNS: tuple[str, ...] = (
    "random seed",
    "pythonhashseed",
    "hashseed",
    "uuid4",
    "uuid.uuid4",
    "nondeterministic",
    "non-deterministic",
    "ordering inconsistent",
    "dict ordering",
    "set ordering",
    "hash randomis",
    "hash randomiz",
)


# ---------------------------------------------------------------------------
# Core classifier
# ---------------------------------------------------------------------------


def _score_category(
    error_msgs: list[str],
    patterns: tuple[str, ...],
) -> float:
    """Return a score in ``[0, 1]`` based on how many error messages match any pattern."""
    if not error_msgs or not patterns:
        return 0.0
    matches = sum(
        1
        for msg in error_msgs
        if any(pat in msg.lower() for pat in patterns)
    )
    return matches / len(error_msgs)


def classify_flake(
    record: FlakeRecord,
    outcomes: Sequence[TestOutcome],
) -> FlakeClassification:
    """Classify the root cause of a flaky test.

    Collects error messages from failing outcomes and scores them against
    each category's pattern table.  The highest-scoring category wins;
    ties break in pattern-table order (TIMING → ORDERING → RESOURCE → RANDOM).

    Args:
        record:   Aggregated :class:`FlakeRecord` for the test.
        outcomes: All :class:`TestOutcome` objects for this test (pass and fail).

    Returns:
        A :class:`FlakeClassification` with the detected category and confidence.
    """
    failing_msgs = [
        o.error_msg
        for o in outcomes
        if not o.passed and o.error_msg
    ]

    if not failing_msgs:
        return FlakeClassification(
            test_id=record.test_id,
            category=FlakeCategory.UNKNOWN,
            confidence=1.0,
            reason="No error messages available for classification.",
        )

    scores: dict[FlakeCategory, float] = {
        FlakeCategory.TIMING:   _score_category(failing_msgs, _TIMING_PATTERNS),
        FlakeCategory.ORDERING: _score_category(failing_msgs, _ORDERING_PATTERNS),
        FlakeCategory.RESOURCE: _score_category(failing_msgs, _RESOURCE_PATTERNS),
        FlakeCategory.RANDOM:   _score_category(failing_msgs, _RANDOM_PATTERNS),
    }

    best_cat, best_score = max(scores.items(), key=lambda kv: kv[1])

    if best_score == 0.0:
        return FlakeClassification(
            test_id=record.test_id,
            category=FlakeCategory.UNKNOWN,
            confidence=1.0,
            reason=f"No known pattern matched. Sample error: {failing_msgs[0][:120]}",
        )

    # Build reason from the highest-scoring message sample
    sample = failing_msgs[0][:120]
    return FlakeClassification(
        test_id=record.test_id,
        category=best_cat,
        confidence=round(best_score, 2),
        reason=f"{best_cat.value.capitalize()} pattern detected. Sample: {sample}",
    )


def classify_many(
    records: list[FlakeRecord],
    outcomes_map: dict[str, list[TestOutcome]],
) -> list[FlakeClassification]:
    """Classify multiple flaky tests.

    Args:
        records:      List of :class:`FlakeRecord` objects to classify.
        outcomes_map: Mapping of ``test_id → list[TestOutcome]``.
                      Missing entries are treated as empty (UNKNOWN).

    Returns:
        One :class:`FlakeClassification` per record, in the same order.
    """
    return [
        classify_flake(rec, outcomes_map.get(rec.test_id, []))
        for rec in records
    ]
