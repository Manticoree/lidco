"""Time Tracker — track time per task, auto-detect from git activity, reports, export."""

from __future__ import annotations

import datetime
import json
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class TimeEntry:
    """A single time tracking entry."""

    task: str
    project: str
    start: datetime.datetime
    end: Optional[datetime.datetime] = None
    tags: tuple[str, ...] = ()

    def duration(self) -> datetime.timedelta:
        """Return duration of this entry."""
        end = self.end if self.end is not None else datetime.datetime.now(tz=datetime.timezone.utc)
        return end - self.start

    def with_end(self, end: datetime.datetime) -> TimeEntry:
        """Return a new entry with the given end time."""
        return TimeEntry(
            task=self.task,
            project=self.project,
            start=self.start,
            end=end,
            tags=self.tags,
        )

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "task": self.task,
            "project": self.project,
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "tags": list(self.tags),
        }

    @staticmethod
    def from_dict(data: dict) -> TimeEntry:
        """Deserialize from dictionary."""
        return TimeEntry(
            task=data["task"],
            project=data["project"],
            start=datetime.datetime.fromisoformat(data["start"]),
            end=datetime.datetime.fromisoformat(data["end"]) if data.get("end") else None,
            tags=tuple(data.get("tags", ())),
        )


@dataclass
class ProjectAllocation:
    """Time allocation for a project."""

    project: str
    total_seconds: float
    entry_count: int
    tasks: List[str]


@dataclass
class TimeReport:
    """A time tracking report."""

    period_start: datetime.datetime
    period_end: datetime.datetime
    allocations: List[ProjectAllocation]
    total_seconds: float

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines = [
            f"Time Report: {self.period_start.date()} to {self.period_end.date()}",
            f"Total: {_format_duration(self.total_seconds)}",
            "",
        ]
        for alloc in sorted(self.allocations, key=lambda a: a.total_seconds, reverse=True):
            pct = (alloc.total_seconds / self.total_seconds * 100) if self.total_seconds > 0 else 0
            lines.append(
                f"  {alloc.project}: {_format_duration(alloc.total_seconds)} "
                f"({pct:.0f}%) — {alloc.entry_count} entries"
            )
        return "\n".join(lines)


def _format_duration(seconds: float) -> str:
    """Format seconds as Xh Ym."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


class TimeTracker:
    """Track time per task with git auto-detection and reporting."""

    def __init__(self) -> None:
        self._entries: List[TimeEntry] = []
        self._active: Optional[TimeEntry] = None

    @property
    def entries(self) -> List[TimeEntry]:
        """Return all completed entries."""
        return list(self._entries)

    @property
    def active(self) -> Optional[TimeEntry]:
        """Return the currently active entry, if any."""
        return self._active

    def start(
        self,
        task: str,
        project: str = "default",
        tags: Optional[List[str]] = None,
    ) -> TimeEntry:
        """Start tracking a new task. Stops any active task first."""
        if self._active is not None:
            self.stop()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        entry = TimeEntry(
            task=task,
            project=project,
            start=now,
            tags=tuple(tags or []),
        )
        self._active = entry
        return entry

    def stop(self) -> Optional[TimeEntry]:
        """Stop the active task and return the completed entry."""
        if self._active is None:
            return None
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        completed = self._active.with_end(now)
        self._entries.append(completed)
        self._active = None
        return completed

    def detect_from_git(self, repo_path: str = ".", limit: int = 20) -> List[TimeEntry]:
        """Auto-detect time entries from recent git commits."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{limit}", "--format=%H|%aI|%s"],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=10,
            )
            if result.returncode != 0:
                return []
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return []

        entries: List[TimeEntry] = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            _hash, iso_date, subject = parts
            try:
                commit_time = datetime.datetime.fromisoformat(iso_date)
            except ValueError:
                continue
            entry = TimeEntry(
                task=subject,
                project=_detect_project(repo_path),
                start=commit_time,
                end=commit_time,
                tags=("git",),
            )
            entries.append(entry)
        return entries

    def report(
        self,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> TimeReport:
        """Generate a time report for the given period."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        period_start = start or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        period_end = end or now

        filtered = [
            e for e in self._entries
            if e.start >= period_start and e.start <= period_end
        ]

        projects: Dict[str, List[TimeEntry]] = {}
        for e in filtered:
            projects.setdefault(e.project, []).append(e)

        allocations: List[ProjectAllocation] = []
        total = 0.0
        for proj, proj_entries in projects.items():
            secs = sum(e.duration().total_seconds() for e in proj_entries)
            total += secs
            tasks = list({e.task for e in proj_entries})
            allocations.append(ProjectAllocation(
                project=proj,
                total_seconds=secs,
                entry_count=len(proj_entries),
                tasks=tasks,
            ))

        return TimeReport(
            period_start=period_start,
            period_end=period_end,
            allocations=allocations,
            total_seconds=total,
        )

    def export_json(self) -> str:
        """Export all entries as JSON."""
        data = [e.to_dict() for e in self._entries]
        return json.dumps(data, indent=2)

    def import_json(self, raw: str) -> int:
        """Import entries from JSON. Returns count imported."""
        data = json.loads(raw)
        count = 0
        for item in data:
            entry = TimeEntry.from_dict(item)
            self._entries.append(entry)
            count += 1
        return count


def _detect_project(repo_path: str) -> str:
    """Detect project name from git remote or directory name."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            url = result.stdout.strip()
            name = url.rstrip("/").rsplit("/", 1)[-1]
            if name.endswith(".git"):
                name = name[:-4]
            return name
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    import os
    return os.path.basename(os.path.abspath(repo_path))
