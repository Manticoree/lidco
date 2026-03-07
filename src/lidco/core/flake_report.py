"""Flake report formatter — produces Markdown summaries of flaky test analysis.

Usage::

    from lidco.core.flake_report import format_flake_report

    report = format_flake_report(
        history,
        flaky_records=result.flaky_tests,
        classifications=classify_many(result.flaky_tests, outcomes_map),
        run_errors=result.run_errors,
    )
    print(report)
"""

from __future__ import annotations

from lidco.core.flake_classifier import FlakeCategory, FlakeClassification
from lidco.core.flake_detector import FlakeHistory, FlakeRecord


# ---------------------------------------------------------------------------
# Summary line
# ---------------------------------------------------------------------------


def format_flake_summary(
    history: FlakeHistory,
    flaky_records: list[FlakeRecord],
) -> str:
    """Return a one-line summary of the flake detection session.

    Args:
        history:        Full :class:`FlakeHistory`.
        flaky_records:  Flaky tests identified (already filtered by threshold).

    Returns:
        A single-line Markdown string.
    """
    n_flaky = len(flaky_records)
    n_tests = history.total_tests
    n_runs = history.total_runs

    if n_flaky == 0:
        return (
            f"[OK] No flaky tests detected — "
            f"{n_tests} test(s) across {n_runs} total execution(s)."
        )
    return (
        f"Flake Report: {n_flaky} flaky test(s) out of {n_tests} "
        f"({n_runs} total execution(s))."
    )


# ---------------------------------------------------------------------------
# Full report
# ---------------------------------------------------------------------------


def format_flake_report(
    history: FlakeHistory,
    flaky_records: list[FlakeRecord],
    classifications: list[FlakeClassification],
    run_errors: list[str] | None = None,
) -> str:
    """Format a full Markdown flake detection report.

    Args:
        history:         Full :class:`FlakeHistory`.
        flaky_records:   Flaky tests sorted by flake rate descending.
        classifications: One :class:`FlakeClassification` per flaky record
                         (same order).  May be shorter than *flaky_records*
                         if classification was partial.
        run_errors:      Optional list of error messages from failed runs.

    Returns:
        A multi-line Markdown string.
    """
    lines: list[str] = ["# Flaky Test Report", ""]

    # ── Summary ──────────────────────────────────────────────────────────
    lines.append(format_flake_summary(history, flaky_records))
    lines.append("")

    # ── Run errors ────────────────────────────────────────────────────────
    if run_errors:
        lines.append("## Run Errors")
        lines.append("")
        for err in run_errors:
            lines.append(f"- {err}")
        lines.append("")

    # ── Flaky test table ──────────────────────────────────────────────────
    if not flaky_records:
        return "\n".join(lines).strip()

    lines.append("## Flaky Tests")
    lines.append("")
    lines.append("| Test | Runs | Failures | Flake Rate | Category | Confidence |")
    lines.append("|------|------|----------|------------|----------|------------|")

    # Build a lookup from test_id → classification
    clf_map: dict[str, FlakeClassification] = {
        c.test_id: c for c in classifications
    }

    for rec in flaky_records:
        clf = clf_map.get(rec.test_id)
        category = clf.category.value if clf else FlakeCategory.UNKNOWN.value
        confidence = f"{clf.confidence:.0%}" if clf else "—"
        rate_pct = f"{rec.flake_rate:.0%}"
        # Truncate long test IDs for table readability
        tid = rec.test_id if len(rec.test_id) <= 60 else "…" + rec.test_id[-57:]
        lines.append(
            f"| `{tid}` | {rec.runs} | {rec.failures} "
            f"| {rate_pct} | {category} | {confidence} |"
        )

    lines.append("")

    # ── Per-test detail ────────────────────────────────────────────────────
    if classifications:
        lines.append("## Classification Details")
        lines.append("")
        for clf in classifications:
            lines.append(f"### `{clf.test_id}`")
            lines.append(f"- **Category:** {clf.category.value}")
            lines.append(f"- **Confidence:** {clf.confidence:.0%}")
            lines.append(f"- **Reason:** {clf.reason}")
            lines.append("")

    return "\n".join(lines).rstrip()
