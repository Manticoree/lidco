"""Read pytest/coverage.py test coverage data for injection into agent context.

Supports two modes:
1. Pre-generated JSON: reads ``.lidco/coverage.json`` if it already exists.
2. On-demand generation: runs ``python -m coverage json -o .lidco/coverage.json``
   against an existing ``.coverage`` data file.

When neither is available the module returns an empty string so callers can
safely include the result without special-casing the "no coverage" state.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_COVERAGE_JSON_PATH = Path(".lidco") / "coverage.json"
_COVERAGE_DATA_FILE = Path(".coverage")
_MAX_FILES_IN_CONTEXT = 15   # cap to avoid bloating the system prompt


def _run_coverage_json(project_dir: Path, output_path: Path) -> bool:
    """Run ``python -m coverage json`` to produce a JSON report.

    Returns True on success, False if coverage is not installed or data file
    is missing.
    """
    data_file = project_dir / _COVERAGE_DATA_FILE
    if not data_file.exists():
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["python", "-m", "coverage", "json", "-o", str(output_path)],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("coverage json failed: %s", exc)
        return False


def _parse_coverage_json(json_path: Path) -> dict[str, float]:
    """Return {relative_path: pct_covered} from a coverage JSON file.

    Paths in the JSON are absolute; we normalise them to be relative to the
    parent directory of ``.lidco/``.
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Cannot read coverage JSON at %s: %s", json_path, exc)
        return {}

    project_dir = json_path.parent.parent  # .lidco/../  = project root
    result: dict[str, float] = {}

    for abs_path, file_data in data.get("files", {}).items():
        pct = file_data.get("summary", {}).get("percent_covered", None)
        if pct is None:
            continue
        try:
            rel = Path(abs_path).relative_to(project_dir)
            result[str(rel).replace("\\", "/")] = round(pct, 1)
        except ValueError:
            # Path is outside project — use basename only
            result[Path(abs_path).name] = round(pct, 1)

    return result


def read_coverage(project_dir: Path) -> dict[str, float]:
    """Return per-file coverage percentages for *project_dir*.

    Reads from ``.lidco/coverage.json`` if present; otherwise tries to
    generate it from ``.coverage``.  Returns an empty dict when no coverage
    data is available.
    """
    json_path = project_dir / _COVERAGE_JSON_PATH

    if not json_path.exists():
        _run_coverage_json(project_dir, json_path)

    if not json_path.exists():
        return {}

    return _parse_coverage_json(json_path)


def build_coverage_context(
    project_dir: Path,
    *,
    limit: int = _MAX_FILES_IN_CONTEXT,
    low_threshold: float = 60.0,
) -> str:
    """Return a compact ``## Test Coverage`` section for agent injection.

    Shows the *limit* files with the lowest coverage first so agents focus
    attention where it matters most.  Files above 100% threshold are omitted
    to keep the section token-efficient.

    Returns an empty string when no coverage data is found.
    """
    data = read_coverage(project_dir)
    if not data:
        return ""

    # Sort by coverage ascending (least covered first)
    sorted_files = sorted(data.items(), key=lambda kv: kv[1])

    lines = ["## Test Coverage\n"]

    shown = 0
    low_count = sum(1 for _, pct in sorted_files if pct < low_threshold)

    for path, pct in sorted_files:
        if shown >= limit:
            remaining = len(sorted_files) - shown
            lines.append(f"  ... ({remaining} more files)")
            break
        bar = "▓" * int(pct / 10) + "░" * (10 - int(pct / 10))
        flag = " ⚠" if pct < low_threshold else ""
        lines.append(f"  {pct:5.1f}%  [{bar}]  {path}{flag}")
        shown += 1

    if low_count:
        lines.append(f"\n{low_count} file(s) below {low_threshold:.0f}% coverage threshold.")

    overall = data.get("", None)  # some reporters include an overall key
    if overall is None and data:
        overall = round(sum(data.values()) / len(data), 1)
    if overall is not None:
        lines.append(f"Overall average: {overall:.1f}%")

    return "\n".join(lines)
