"""Coverage gap locator — find uncovered lines and branches for a file.

Parses the coverage.py JSON report format (``coverage json``) and surfaces
which lines and branches were not executed so the debugger can focus attention
on the least-tested code paths.

Usage::

    from lidco.core.coverage_gap import parse_coverage_json, find_gaps_for_file, format_coverage_gaps

    with open(".lidco/coverage.json") as f:
        data = json.load(f)

    coverage_map = parse_coverage_json(data)
    gap = find_gaps_for_file("src/lidco/core/session.py", coverage_map)
    if gap:
        print(format_coverage_gaps([gap]))
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileCoverageInfo:
    """Per-file coverage details extracted from a coverage JSON report.

    Attributes:
        file_path:        Relative file path as it appears in the JSON (key).
        executed_lines:   Lines that were executed during test runs.
        missing_lines:    Lines that were **not** executed.
        excluded_lines:   Lines excluded by ``# pragma: no cover`` or config.
        missing_branches: Pairs ``(from_line, to_line)`` for unexecuted branches.
        coverage_pct:     Statement coverage percentage in ``[0.0, 100.0]``.
    """

    file_path: str
    executed_lines: list[int]
    missing_lines: list[int]
    excluded_lines: list[int]
    missing_branches: list[tuple[int, int]]
    coverage_pct: float


@dataclass(frozen=True)
class CoverageGap:
    """Uncovered lines and branches for a single source file.

    Attributes:
        file_path:        Source file path.
        missing_lines:    Line numbers with no execution.
        missing_branches: ``(from_line, to_line)`` pairs for unexecuted branches.
        coverage_pct:     Statement coverage percentage (lower = more gaps).
    """

    file_path: str
    missing_lines: list[int]
    missing_branches: list[tuple[int, int]]
    coverage_pct: float


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_coverage_json(data: dict) -> dict[str, FileCoverageInfo]:
    """Parse a coverage.py JSON report dict into a map of :class:`FileCoverageInfo`.

    The *data* dict is expected to have the shape produced by ``coverage json``::

        {
            "files": {
                "src/foo.py": {
                    "executed_lines": [...],
                    "missing_lines": [...],
                    "excluded_lines": [...],
                    "missing_branches": [[from, to], ...],
                    "summary": {"percent_covered": 80.0}
                }
            }
        }

    Missing or malformed keys are handled gracefully (defaults to empty lists /
    zero percentage).  Returns an empty dict for entirely malformed input.
    """
    files_raw = data.get("files")
    if not isinstance(files_raw, dict):
        return {}

    result: dict[str, FileCoverageInfo] = {}
    for path, file_data in files_raw.items():
        if not isinstance(file_data, dict):
            continue

        executed = list(file_data.get("executed_lines") or [])
        missing = list(file_data.get("missing_lines") or [])
        excluded = list(file_data.get("excluded_lines") or [])
        pct = float(
            (file_data.get("summary") or {}).get("percent_covered", 0.0)
        )

        raw_branches = file_data.get("missing_branches") or []
        branches: list[tuple[int, int]] = []
        for b in raw_branches:
            if isinstance(b, (list, tuple)) and len(b) >= 2:
                branches.append((int(b[0]), int(b[1])))

        result[path] = FileCoverageInfo(
            file_path=path,
            executed_lines=executed,
            missing_lines=missing,
            excluded_lines=excluded,
            missing_branches=branches,
            coverage_pct=pct,
        )
    return result


# ---------------------------------------------------------------------------
# Gap lookup
# ---------------------------------------------------------------------------


def find_gaps_for_file(
    file_path: str,
    coverage_map: dict[str, FileCoverageInfo],
) -> CoverageGap | None:
    """Return a :class:`CoverageGap` for *file_path*, or ``None`` if no gaps.

    Normalises path separators so both ``src/foo.py`` and ``src\\foo.py`` match
    the same entry.  Returns ``None`` when the file is not in *coverage_map* or
    has no missing lines or branches.
    """
    normalised = file_path.replace("\\", "/")

    info: FileCoverageInfo | None = None
    # Exact match first
    if normalised in coverage_map:
        info = coverage_map[normalised]
    else:
        # Fallback: try backslash variant
        bs = file_path.replace("/", "\\")
        info = coverage_map.get(bs)

    if info is None:
        return None

    if not info.missing_lines and not info.missing_branches:
        return None

    return CoverageGap(
        file_path=info.file_path,
        missing_lines=info.missing_lines,
        missing_branches=info.missing_branches,
        coverage_pct=info.coverage_pct,
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

_MAX_LINES_SHOWN = 20
_MAX_BRANCHES_SHOWN = 10


def format_coverage_gaps(gaps: list[CoverageGap]) -> str:
    """Format *gaps* as a Markdown section suitable for agent context injection.

    Files with lower coverage are listed first (most attention needed).
    Returns a brief "[OK] No coverage gaps found." when *gaps* is empty.
    """
    if not gaps:
        return "[OK] No coverage gaps found."

    sorted_gaps = sorted(gaps, key=lambda g: g.coverage_pct)

    lines: list[str] = ["## Coverage Gaps\n"]
    for gap in sorted_gaps:
        lines.append(f"### `{gap.file_path}` — {gap.coverage_pct:.1f}% covered\n")

        if gap.missing_lines:
            shown = gap.missing_lines[:_MAX_LINES_SHOWN]
            suffix = (
                f" … ({len(gap.missing_lines) - _MAX_LINES_SHOWN} more)"
                if len(gap.missing_lines) > _MAX_LINES_SHOWN
                else ""
            )
            lines.append(f"**Uncovered lines:** {', '.join(str(l) for l in shown)}{suffix}\n")

        if gap.missing_branches:
            shown_br = gap.missing_branches[:_MAX_BRANCHES_SHOWN]
            suffix_br = (
                f" … ({len(gap.missing_branches) - _MAX_BRANCHES_SHOWN} more)"
                if len(gap.missing_branches) > _MAX_BRANCHES_SHOWN
                else ""
            )
            branch_strs = [f"{f}→{t}" for f, t in shown_br]
            lines.append(f"**Uncovered branches:** {', '.join(branch_strs)}{suffix_br}\n")

    return "\n".join(lines)
