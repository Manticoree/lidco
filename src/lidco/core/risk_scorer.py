"""Unified file risk score — combines complexity, churn, coverage, and error history.

Produces a single 0–100 score per file that aggregates four orthogonal dimensions:

- **Complexity** (0–25): LOC / function count from ``_compute_file_metrics``
- **Churn** (0–25): recent commit count from ``git log``
- **Coverage** (0–25): statement coverage from ``FileCoverageInfo.coverage_pct``
- **Error history** (0–25): occurrences of the file in the cross-session ledger

Usage::

    from lidco.core.risk_scorer import compute_all_risk_scores, format_risk_report

    scores = compute_all_risk_scores(project_dir, ledger, coverage_map)
    print(format_risk_report(scores))
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lidco.core.coverage_gap import FileCoverageInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskDimension:
    """A single scored dimension of file risk.

    Attributes:
        score:  Points contributed to the total (0–25).
        reason: Human-readable explanation of the score.
    """

    score: int   # 0–25 points
    reason: str  # human explanation


@dataclass(frozen=True)
class RiskScore:
    """Composite risk score for a single source file.

    Attributes:
        file_path:     Relative path of the scored file.
        total:         Sum of all dimension scores (0–100).
        complexity:    Dimension based on LOC and function count.
        churn:         Dimension based on git commit frequency.
        coverage:      Dimension based on statement coverage percentage.
        error_history: Dimension based on cross-session error occurrences.
        label:         ``"HIGH"`` / ``"MEDIUM"`` / ``"LOW"`` threshold label.
    """

    file_path: str
    total: int
    complexity: RiskDimension
    churn: RiskDimension
    coverage: RiskDimension
    error_history: RiskDimension
    label: str  # "HIGH" / "MEDIUM" / "LOW"


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------


def _score_complexity(metrics: dict[str, Any]) -> RiskDimension:
    """Score a file's structural complexity based on LOC.

    Uses the ``loc`` key from ``_compute_file_metrics()`` output.

    Thresholds:
    - LOC > 400 → 25 (very large)
    - LOC > 200 → 15 (large)
    - LOC > 100 → 5  (moderate)
    - else      → 0  (small)
    """
    loc = metrics.get("loc", 0) or 0
    if loc > 400:
        return RiskDimension(score=25, reason=f"Very large file ({loc} LOC)")
    if loc > 200:
        return RiskDimension(score=15, reason=f"Large file ({loc} LOC)")
    if loc > 100:
        return RiskDimension(score=5, reason=f"Moderate file ({loc} LOC)")
    return RiskDimension(score=0, reason=f"Small file ({loc} LOC)")


def _score_churn(git_log: str) -> RiskDimension:
    """Score churn based on the number of recent commits that touched the file.

    Each non-blank line in *git_log* represents one commit (``git log --oneline``
    output).

    Thresholds:
    - commits ≥ 5 → 25 (very hot)
    - commits ≥ 3 → 15 (hot)
    - commits ≥ 1 → 5  (some churn)
    - else        → 0  (stable)
    """
    commits = len([ln for ln in git_log.splitlines() if ln.strip()]) if git_log else 0
    if commits >= 5:
        return RiskDimension(score=25, reason=f"Very high churn ({commits} recent commits)")
    if commits >= 3:
        return RiskDimension(score=15, reason=f"High churn ({commits} recent commits)")
    if commits >= 1:
        return RiskDimension(score=5, reason=f"Some churn ({commits} recent commits)")
    return RiskDimension(score=0, reason="No recent commits (stable)")


def _score_coverage(
    file_path: str,
    coverage_map: dict[str, "FileCoverageInfo"],
) -> RiskDimension:
    """Score a file's test coverage gap.

    Looks up *file_path* (normalised to forward slashes) in *coverage_map*.
    Thresholds:
    - pct < 40  → 25 (very low)
    - pct < 60  → 15 (low)
    - pct < 80  → 5  (moderate)
    - else      → 0  (well-covered)
    - not found → 0  (unknown — no data)
    """
    normalised = file_path.replace("\\", "/")
    info = coverage_map.get(normalised) or coverage_map.get(file_path.replace("/", "\\"))
    if info is None:
        return RiskDimension(score=0, reason="No coverage data available")

    pct = info.coverage_pct
    if pct < 40:
        return RiskDimension(score=25, reason=f"Very low coverage ({pct:.0f}%)")
    if pct < 60:
        return RiskDimension(score=15, reason=f"Low coverage ({pct:.0f}%)")
    if pct < 80:
        return RiskDimension(score=5, reason=f"Moderate coverage ({pct:.0f}%)")
    return RiskDimension(score=0, reason=f"Well-covered ({pct:.0f}%)")


def _score_error_history(
    file_path: str,
    ledger_entries: list[dict[str, Any]],
) -> RiskDimension:
    """Score a file's presence in the cross-session error ledger.

    *ledger_entries* is the result of ``ErrorLedger.get_recurring()`` or
    ``get_frequent()``.  A match occurs when the filename (without directory
    prefix) appears in the entry's ``sample_message``.

    Thresholds:
    - matches ≥ 5 → 25 (very frequent)
    - matches ≥ 2 → 15 (frequent)
    - matches ≥ 1 → 5  (occasional)
    - else        → 0  (no history)
    """
    basename = Path(file_path).name
    matches = sum(
        1 for e in ledger_entries
        if basename and basename in (e.get("sample_message") or "")
    )
    if matches >= 5:
        return RiskDimension(score=25, reason=f"Frequent in error ledger ({matches} entries)")
    if matches >= 2:
        return RiskDimension(score=15, reason=f"In error ledger ({matches} entries)")
    if matches >= 1:
        return RiskDimension(score=5, reason=f"Occasional in error ledger ({matches} entry)")
    return RiskDimension(score=0, reason="No error history")


def _label(total: int) -> str:
    """Return a risk label for *total* (0–100)."""
    if total >= 60:
        return "HIGH"
    if total >= 30:
        return "MEDIUM"
    return "LOW"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_risk_score(
    file_path: str,
    metrics: dict[str, Any],
    git_log: str,
    coverage_map: dict[str, Any],
    ledger_entries: list[dict[str, Any]],
) -> RiskScore:
    """Compute a composite :class:`RiskScore` for a single file.

    Args:
        file_path:      Relative path of the file (used for coverage / ledger
                        lookup and as the score identifier).
        metrics:        Output of ``_compute_file_metrics()`` for this file.
        git_log:        Raw output of ``git log --oneline -N -- <file>``.
        coverage_map:   ``dict[str, FileCoverageInfo]`` from
                        ``parse_coverage_json()``.
        ledger_entries: List of error dicts from ``ErrorLedger.get_recurring()``.

    Returns:
        A :class:`RiskScore` with all four dimensions populated.
    """
    complexity = _score_complexity(metrics)
    churn = _score_churn(git_log)
    coverage = _score_coverage(file_path, coverage_map)
    error_hist = _score_error_history(file_path, ledger_entries)
    total = complexity.score + churn.score + coverage.score + error_hist.score
    return RiskScore(
        file_path=file_path,
        total=total,
        complexity=complexity,
        churn=churn,
        coverage=coverage,
        error_history=error_hist,
        label=_label(total),
    )


def _get_git_log_for_file(file_path: str, project_dir: Path) -> str:
    """Run ``git log --oneline -10 -- <file>`` and return stdout."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-10", "--", file_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(project_dir),
            timeout=3,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def compute_all_risk_scores(
    project_dir: Path,
    ledger: Any | None,
    coverage_map: dict[str, Any] | None,
) -> list[RiskScore]:
    """Compute :class:`RiskScore` for every ``.py`` file under ``src/`` in *project_dir*.

    Iterates all ``*.py`` files, runs ``_compute_file_metrics`` and
    ``git log`` per-file (synchronously — call via ``run_in_executor`` from
    async code), and returns results sorted by total score descending.

    Args:
        project_dir:  Project root directory.
        ledger:       ``ErrorLedger`` instance (or ``None`` to skip history).
        coverage_map: ``dict[str, FileCoverageInfo]`` or ``None``.
    """
    # Import here to avoid circular imports at module level
    from lidco.agents.graph import GraphOrchestrator

    src_dir = project_dir / "src"
    if not src_dir.exists():
        src_dir = project_dir

    cov_map: dict[str, Any] = coverage_map or {}
    ledger_entries: list[dict[str, Any]] = []
    if ledger is not None:
        try:
            ledger_entries = ledger.get_recurring(min_sessions=1)
        except Exception:
            ledger_entries = []

    scores: list[RiskScore] = []
    py_files = list(src_dir.rglob("*.py"))

    for abs_path in py_files:
        try:
            rel_path = abs_path.relative_to(project_dir)
            rel_str = str(rel_path).replace("\\", "/")
        except ValueError:
            rel_str = str(abs_path)

        try:
            metrics = GraphOrchestrator._compute_file_metrics(str(abs_path))
        except Exception:
            metrics = {}

        git_log = _get_git_log_for_file(rel_str, project_dir)

        score = compute_risk_score(rel_str, metrics, git_log, cov_map, ledger_entries)
        scores.append(score)

    scores.sort(key=lambda s: s.total, reverse=True)
    return scores


def format_risk_report(scores: list[RiskScore], top_n: int = 5) -> str:
    """Format the top-N riskiest files as a Markdown table.

    Returns ``""`` when *scores* is empty or all scores are zero.

    Example output::

        ## High-Risk Files
        | File | Score | Label | Complexity | Churn | Coverage | Errors |
        |------|-------|-------|-----------|-------|---------|--------|
        | src/foo.py | 65 | HIGH | 25 | 15 | 25 | 0 |
    """
    relevant = [s for s in scores if s.total > 0]
    if not relevant:
        return ""

    top = relevant[:top_n]
    lines: list[str] = [
        "## High-Risk Files\n",
        "| File | Score | Label | Complexity | Churn | Coverage | Errors |",
        "|------|-------|-------|-----------|-------|---------|--------|",
    ]
    for s in top:
        lines.append(
            f"| `{s.file_path}` | {s.total} | {s.label} "
            f"| {s.complexity.score} | {s.churn.score} "
            f"| {s.coverage.score} | {s.error_history.score} |"
        )
    return "\n".join(lines)
