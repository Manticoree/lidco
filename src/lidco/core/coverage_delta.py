"""Coverage delta tracker — compute before/after coverage changes.

Compares two coverage snapshots (e.g. before and after a commit) and returns
per-file deltas showing which lines became covered or newly uncovered.

Usage::

    from lidco.core.coverage_delta import compute_delta, format_delta
    from lidco.core.coverage_gap import parse_coverage_json

    before = parse_coverage_json(before_data)
    after  = parse_coverage_json(after_data)
    deltas = compute_delta(before, after)
    print(format_delta(deltas))
"""

from __future__ import annotations

from dataclasses import dataclass

from lidco.core.coverage_gap import FileCoverageInfo


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoverageDelta:
    """Coverage change for a single file between two snapshots.

    Attributes:
        file_path:      Source file path.
        before_pct:     Coverage percentage in the *before* snapshot.
        after_pct:      Coverage percentage in the *after* snapshot.
        delta_pct:      ``after_pct - before_pct`` (positive = improvement).
        newly_covered:  Lines that moved from missing → executed.
        newly_missing:  Lines that moved from executed → missing (regression).
    """

    file_path: str
    before_pct: float
    after_pct: float
    delta_pct: float
    newly_covered: list[int]
    newly_missing: list[int]


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------


def compute_delta(
    before: dict[str, FileCoverageInfo],
    after: dict[str, FileCoverageInfo],
) -> list[CoverageDelta]:
    """Compute per-file coverage deltas between two snapshots.

    Files that appear only in *before* are reported as regressed to 0%.
    Files that appear only in *after* are reported as improved from 0%.
    Files with no change in lines or percentage are **excluded** to keep the
    output concise.

    Args:
        before: Coverage map from the earlier snapshot (from :func:`parse_coverage_json`).
        after:  Coverage map from the later snapshot.

    Returns:
        List of :class:`CoverageDelta` objects, sorted by absolute delta descending
        (largest changes first).
    """
    all_paths = set(before) | set(after)
    deltas: list[CoverageDelta] = []

    for path in all_paths:
        b_info = before.get(path)
        a_info = after.get(path)

        b_pct = b_info.coverage_pct if b_info else 0.0
        a_pct = a_info.coverage_pct if a_info else 0.0

        b_missing = set(b_info.missing_lines) if b_info else set()
        a_missing = set(a_info.missing_lines) if a_info else set()

        b_executed = set(b_info.executed_lines) if b_info else set()
        a_executed = set(a_info.executed_lines) if a_info else set()

        # Lines that were missing before and are now executed
        newly_covered = sorted(b_missing & a_executed)
        # Lines that were executed before and are now missing
        newly_missing = sorted(b_executed & a_missing)

        delta_pct = round(a_pct - b_pct, 2)

        # Skip files with zero change and no line movement
        if delta_pct == 0.0 and not newly_covered and not newly_missing:
            continue

        deltas.append(
            CoverageDelta(
                file_path=path,
                before_pct=b_pct,
                after_pct=a_pct,
                delta_pct=delta_pct,
                newly_covered=newly_covered,
                newly_missing=newly_missing,
            )
        )

    # Sort by abs(delta) descending — biggest changes first
    deltas.sort(key=lambda d: abs(d.delta_pct), reverse=True)
    return deltas


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

_MAX_LINES_SHOWN = 15


def format_delta(deltas: list[CoverageDelta]) -> str:
    """Format *deltas* as a Markdown section for agent context injection.

    Improvements (delta > 0) are marked ✅, regressions (delta < 0) with ⚠.
    Returns a brief "[OK] No coverage changes detected." when *deltas* is empty.
    """
    if not deltas:
        return "[OK] No coverage changes detected."

    lines: list[str] = ["## Coverage Delta\n"]
    for d in deltas:
        sign = "+" if d.delta_pct >= 0 else ""
        icon = "✅" if d.delta_pct > 0 else ("⚠" if d.delta_pct < 0 else "—")
        lines.append(
            f"### {icon} `{d.file_path}` {sign}{d.delta_pct:+.1f}%  "
            f"({d.before_pct:.1f}% → {d.after_pct:.1f}%)\n"
        )
        if d.newly_covered:
            shown = d.newly_covered[:_MAX_LINES_SHOWN]
            suffix = (
                f" … ({len(d.newly_covered) - _MAX_LINES_SHOWN} more)"
                if len(d.newly_covered) > _MAX_LINES_SHOWN
                else ""
            )
            lines.append(
                f"  **Newly covered:** {', '.join(str(l) for l in shown)}{suffix}"
            )
        if d.newly_missing:
            shown_m = d.newly_missing[:_MAX_LINES_SHOWN]
            suffix_m = (
                f" … ({len(d.newly_missing) - _MAX_LINES_SHOWN} more)"
                if len(d.newly_missing) > _MAX_LINES_SHOWN
                else ""
            )
            lines.append(
                f"  **Newly missing:** {', '.join(str(l) for l in shown_m)}{suffix_m}"
            )

    return "\n".join(lines)
