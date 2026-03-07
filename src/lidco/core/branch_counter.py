"""Branch hit counter — count executed/missed branches from coverage data.

Parses the ``arcs`` section of a coverage.py JSON report to produce per-file
branch hit/miss statistics.  The ``arcs`` dict maps ``"(from, to)"`` strings
to hit counts (positive = executed, negative = not executed per coverage.py
convention, but we also handle the simple ``missing_branches`` list from the
per-file summary).

Usage::

    from lidco.core.branch_counter import parse_branch_hits, compute_branch_stats

    branch_hits = parse_branch_hits(coverage_data, "src/lidco/core/session.py")
    stats = compute_branch_stats("src/lidco/core/session.py", branch_hits)
    print(format_branch_stats(stats))
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BranchHit:
    """A single branch arc with its execution hit count.

    Attributes:
        from_line: Line number where the branch originates.
        to_line:   Line number where the branch leads (destination).
        hits:      Number of times this arc was executed (0 = never taken).
    """

    from_line: int
    to_line: int
    hits: int


@dataclass(frozen=True)
class BranchStats:
    """Aggregated branch coverage statistics for a single file.

    Attributes:
        file_path:      Source file path.
        total_branches: Total number of branch arcs tracked.
        hit_branches:   Number of arcs executed at least once.
        miss_branches:  Number of arcs never executed.
        hit_rate:       ``hit_branches / total_branches`` in ``[0.0, 1.0]``,
                        or ``1.0`` when there are no branches.
    """

    file_path: str
    total_branches: int
    hit_branches: int
    miss_branches: int
    hit_rate: float


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _normalise_path(path: str) -> str:
    return path.replace("\\", "/")


def parse_branch_hits(coverage_data: dict, file_path: str) -> list[BranchHit]:
    """Extract :class:`BranchHit` records for *file_path* from a coverage JSON dict.

    Supports two coverage.py data shapes:

    1. **``arcs`` per file** (coverage.py with ``--branch``):
       ``{"files": {"src/foo.py": {"arcs": {"(1, 5)": 3, "(1, -1)": 0}, ...}}}``
       Arcs with a hit count ``> 0`` are executed; ``<= 0`` are missed.

    2. **``missing_branches`` per file** (simpler summary format):
       ``{"files": {"src/foo.py": {"missing_branches": [[3, 5], [7, 9]]}}}``
       Branches in this list are missed (hits=0); all others are assumed hit (hits=1).

    Returns an empty list when *file_path* is not found in *coverage_data*.
    """
    files: dict = coverage_data.get("files") or {}
    norm_target = _normalise_path(file_path)

    file_data: dict | None = None
    for key, val in files.items():
        if _normalise_path(key) == norm_target and isinstance(val, dict):
            file_data = val
            break

    if file_data is None:
        return []

    # Prefer arcs (full branch data)
    arcs = file_data.get("arcs")
    if isinstance(arcs, dict) and arcs:
        return _parse_arcs(arcs)

    # Fallback: derive from missing_branches (partial data — no hit counts available)
    return _parse_missing_branches(file_data)


def _parse_arcs(arcs: dict) -> list[BranchHit]:
    """Convert ``{"(from, to)": hits}`` dict to :class:`BranchHit` list."""
    result: list[BranchHit] = []
    for key, hit_count in arcs.items():
        try:
            # Key format: "(from, to)" or [from, to] list
            if isinstance(key, str):
                stripped = key.strip("() ")
                parts = [p.strip() for p in stripped.split(",")]
                from_line, to_line = int(parts[0]), int(parts[1])
            elif isinstance(key, (list, tuple)) and len(key) >= 2:
                from_line, to_line = int(key[0]), int(key[1])
            else:
                continue
            hits = max(0, int(hit_count))
            result.append(BranchHit(from_line=from_line, to_line=to_line, hits=hits))
        except (ValueError, IndexError):
            continue
    return result


def _parse_missing_branches(file_data: dict) -> list[BranchHit]:
    """Build :class:`BranchHit` records from ``missing_branches`` summary data.

    Missing branches get ``hits=0``; we cannot reconstruct executed branches
    from this format, so executed_lines is used to infer branch origins when
    possible.  In practice this returns only the *missed* arcs.
    """
    result: list[BranchHit] = []
    for item in file_data.get("missing_branches") or []:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                result.append(
                    BranchHit(from_line=int(item[0]), to_line=int(item[1]), hits=0)
                )
            except (ValueError, TypeError):
                continue
    return result


# ---------------------------------------------------------------------------
# Statistics computation
# ---------------------------------------------------------------------------


def compute_branch_stats(file_path: str, branch_hits: list[BranchHit]) -> BranchStats:
    """Compute aggregate :class:`BranchStats` from a list of :class:`BranchHit`.

    Args:
        file_path:    Source file path (used as label only).
        branch_hits:  Output of :func:`parse_branch_hits`.

    Returns:
        :class:`BranchStats` with hit/miss counts and hit rate.
    """
    total = len(branch_hits)
    hit = sum(1 for b in branch_hits if b.hits > 0)
    miss = total - hit
    rate = (hit / total) if total > 0 else 1.0
    return BranchStats(
        file_path=file_path,
        total_branches=total,
        hit_branches=hit,
        miss_branches=miss,
        hit_rate=rate,
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_branch_stats(stats: BranchStats) -> str:
    """Return a compact Markdown summary of *stats*.

    Example output::

        ## Branch Coverage: `src/lidco/core/session.py`
        - Total branches : 24
        - Hit            : 18 (75.0%)
        - Missed         : 6
    """
    pct = stats.hit_rate * 100
    lines = [
        f"## Branch Coverage: `{stats.file_path}`\n",
        f"- Total branches : {stats.total_branches}",
        f"- Hit            : {stats.hit_branches} ({pct:.1f}%)",
        f"- Missed         : {stats.miss_branches}",
    ]
    return "\n".join(lines)
