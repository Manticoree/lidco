"""Daily Standup — generate standup notes from git commits, plans, and blockers."""

from __future__ import annotations

import datetime
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class CommitInfo:
    """A git commit summary."""

    hash: str
    date: datetime.datetime
    subject: str
    author: str


@dataclass(frozen=True)
class StandupNote:
    """A daily standup note."""

    date: datetime.date
    yesterday: List[str]
    today: List[str]
    blockers: List[str]
    commits: List[CommitInfo] = field(default_factory=list)

    def format(self) -> str:
        """Format standup as readable text."""
        lines = [f"Standup — {self.date.isoformat()}", ""]

        lines.append("Yesterday:")
        if self.yesterday:
            for item in self.yesterday:
                lines.append(f"  - {item}")
        else:
            lines.append("  (no items)")

        lines.append("")
        lines.append("Today:")
        if self.today:
            for item in self.today:
                lines.append(f"  - {item}")
        else:
            lines.append("  (no items)")

        lines.append("")
        lines.append("Blockers:")
        if self.blockers:
            for item in self.blockers:
                lines.append(f"  - {item}")
        else:
            lines.append("  (none)")

        if self.commits:
            lines.append("")
            lines.append(f"Commits ({len(self.commits)}):")
            for c in self.commits:
                lines.append(f"  [{c.hash[:7]}] {c.subject}")

        return "\n".join(lines)


class StandupGenerator:
    """Generate daily standup notes from git activity and manual input."""

    def __init__(self) -> None:
        self._plans: List[str] = []
        self._blockers: List[str] = []

    def set_plans(self, plans: List[str]) -> None:
        """Set today's plan items."""
        self._plans = list(plans)

    def add_plan(self, item: str) -> None:
        """Add a single plan item."""
        self._plans.append(item)

    def set_blockers(self, blockers: List[str]) -> None:
        """Set current blockers."""
        self._blockers = list(blockers)

    def add_blocker(self, item: str) -> None:
        """Add a single blocker."""
        self._blockers.append(item)

    def clear(self) -> None:
        """Clear plans and blockers."""
        self._plans.clear()
        self._blockers.clear()

    def get_yesterday_commits(
        self,
        repo_path: str = ".",
        author: Optional[str] = None,
    ) -> List[CommitInfo]:
        """Fetch commits from yesterday."""
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        since = yesterday.isoformat()
        until = datetime.date.today().isoformat()
        return self._fetch_commits(repo_path, since, until, author)

    def get_commits_since(
        self,
        repo_path: str = ".",
        since: Optional[str] = None,
        until: Optional[str] = None,
        author: Optional[str] = None,
    ) -> List[CommitInfo]:
        """Fetch commits for a date range."""
        return self._fetch_commits(repo_path, since, until, author)

    def _fetch_commits(
        self,
        repo_path: str,
        since: Optional[str],
        until: Optional[str],
        author: Optional[str],
    ) -> List[CommitInfo]:
        """Fetch commits using git log."""
        cmd = ["git", "log", "--format=%H|%aI|%an|%s"]
        if since:
            cmd.append(f"--since={since}")
        if until:
            cmd.append(f"--until={until}")
        if author:
            cmd.append(f"--author={author}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=10,
            )
            if result.returncode != 0:
                return []
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return []

        commits: List[CommitInfo] = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 3)
            if len(parts) < 4:
                continue
            h, iso_date, auth, subject = parts
            try:
                dt = datetime.datetime.fromisoformat(iso_date)
            except ValueError:
                continue
            commits.append(CommitInfo(hash=h, date=dt, subject=subject, author=auth))
        return commits

    def generate(
        self,
        repo_path: str = ".",
        author: Optional[str] = None,
        date: Optional[datetime.date] = None,
    ) -> StandupNote:
        """Generate a standup note with yesterday's commits and today's plan."""
        target_date = date or datetime.date.today()
        commits = self.get_yesterday_commits(repo_path, author)
        yesterday_items = [c.subject for c in commits] if commits else ["No commits found"]

        return StandupNote(
            date=target_date,
            yesterday=yesterday_items,
            today=list(self._plans) if self._plans else ["(set plans with /standup plan)"],
            blockers=list(self._blockers),
            commits=commits,
        )

    def format_slack(self, note: StandupNote) -> str:
        """Format standup for Slack (markdown)."""
        lines = [f"*Standup — {note.date.isoformat()}*", ""]

        lines.append("*Yesterday:*")
        for item in note.yesterday:
            lines.append(f"• {item}")

        lines.append("\n*Today:*")
        for item in note.today:
            lines.append(f"• {item}")

        if note.blockers:
            lines.append("\n*Blockers:*")
            for item in note.blockers:
                lines.append(f"• :warning: {item}")

        return "\n".join(lines)
