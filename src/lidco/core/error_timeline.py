"""Error timeline builder — groups errors by time window and correlates with git commits."""
from __future__ import annotations

import asyncio
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


def _make_bar(count: int, width: int = 6) -> str:
    """Build an ASCII bar of *width* chars using ▓ and ░ symbols.

    count == 0  → all ░
    count >= 6  → all ▓
    else        → count ▓s followed by (width - count) ░s
    """
    if count <= 0:
        return "░" * width
    filled = min(count, width)
    return "▓" * filled + "░" * (width - filled)


def _bucket_key(ts: datetime, window_minutes: int) -> datetime:
    """Return the start of the time bucket containing *ts*."""
    minute_floor = (ts.minute // window_minutes) * window_minutes
    return ts.replace(minute=minute_floor, second=0, microsecond=0)


def _get_recent_commits(minutes: int, project_dir: Path | None) -> list[str]:
    """Return git log lines from the last *minutes* minutes.

    Returns an empty list on any error or if git is unavailable.
    """
    try:
        cwd = str(project_dir) if project_dir else None
        result = subprocess.run(
            [
                "git",
                "log",
                "--oneline",
                f"--after={minutes} minutes ago",
                "--format=%h %s (%ai)",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            return [ln for ln in result.stdout.splitlines() if ln.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return []


def build_timeline(
    records: list[Any],  # list of ErrorRecord
    window_minutes: int = 5,
    project_dir: Path | None = None,
) -> str:
    """Build ASCII timeline of errors grouped by time windows.

    Returns a Rich-compatible Markdown string showing:
    - Time buckets (5-min default) with bar charts
    - Error type distribution per bucket
    - Git commits correlated with error spikes
    """
    if not records:
        return "No error data"

    # Determine the time range (last 30 minutes from the most recent record)
    now = max(r.timestamp for r in records)
    # Normalise to UTC-aware if naive
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    window_start = now - timedelta(minutes=30)

    # Group records into buckets
    buckets: dict[datetime, list[Any]] = defaultdict(list)
    for record in records:
        ts = record.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= window_start:
            key = _bucket_key(ts, window_minutes)
            buckets[key].append(record)

    # Generate all bucket keys in the window (even empty ones)
    all_keys: list[datetime] = []
    cursor = _bucket_key(window_start, window_minutes)
    end_key = _bucket_key(now, window_minutes)
    while cursor <= end_key:
        all_keys.append(cursor)
        cursor = cursor + timedelta(minutes=window_minutes)

    # Calculate average for spike detection
    counts = [len(buckets.get(k, [])) for k in all_keys]
    avg_count = sum(counts) / len(counts) if counts else 0

    # Fetch git commits for the last 30 minutes
    commits = _get_recent_commits(30, project_dir)

    # Build output lines
    header_label = f"{window_minutes}-min buckets"
    lines: list[str] = [
        f"Error Timeline (last 30 min, {header_label})",
        "",
    ]

    spike_buckets: list[datetime] = []
    for key in all_keys:
        bucket_records = buckets.get(key, [])
        count = len(bucket_records)
        bar = _make_bar(count)
        time_str = key.strftime("%H:%M")

        # Build error type distribution
        type_counts: dict[str, int] = defaultdict(int)
        for rec in bucket_records:
            error_type = getattr(rec, "error_type", "unknown")
            type_counts[error_type] += 1

        type_parts = sorted(
            (f"{et}×{cnt}" for et, cnt in type_counts.items()),
            key=lambda s: -int(s.split("×")[-1]),
        )
        type_str = ", ".join(type_parts)

        if count > 0:
            label = f"{count} error{'s' if count != 1 else ''}"
            if type_str:
                label += f"  ({type_str})"
        else:
            label = "no errors"

        lines.append(f"{time_str} {bar}  {label}")

        if count > avg_count * 1.5 and count > 1:
            spike_buckets.append(key)

    # Correlate commits with spikes
    if commits and spike_buckets:
        lines.append("")
        lines.append("## Git Commits (last 30 min)")
        for commit_line in commits[:10]:
            lines.append(f"  {commit_line}")

        if spike_buckets:
            lines.append("")
            lines.append("## Spike Correlation")
            for spike_key in spike_buckets:
                lines.append(
                    f"  Error spike at {spike_key.strftime('%H:%M')} "
                    f"({len(buckets[spike_key])} errors)"
                )
    elif commits:
        lines.append("")
        lines.append("## Git Commits (last 30 min)")
        for commit_line in commits[:10]:
            lines.append(f"  {commit_line}")

    return "\n".join(lines)
