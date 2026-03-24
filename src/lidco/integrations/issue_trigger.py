"""IssueTrigger — poll GitHub Issues and trigger agent on assignment."""
from __future__ import annotations

import subprocess
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class Issue:
    number: int
    title: str
    body: str
    url: str
    labels: list[str] = field(default_factory=list)


class IssueTrigger:
    """Poll GitHub Issues for newly assigned items and trigger agent."""

    def __init__(
        self,
        assignee: str = "@me",
        label: str = "lidco",
        project_dir: Path | None = None,
        on_issue: Callable[[Issue], None] | None = None,
    ) -> None:
        self._assignee = assignee
        self._label = label
        self._project_dir = project_dir or Path.cwd()
        self._on_issue = on_issue
        self._seen: set[int] = set()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def poll(self) -> list[Issue]:
        """Return newly assigned issues since last poll."""
        all_issues = self._fetch_issues()
        new_issues = [i for i in all_issues if i.number not in self._seen]
        for issue in new_issues:
            self._seen.add(issue.number)
        return new_issues

    def _fetch_issues(self) -> list[Issue]:
        cmd = ["gh", "issue", "list", "--assignee", self._assignee, "--label", self._label, "--json",
               "number,title,body,url,labels"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=self._project_dir)
            if result.returncode != 0:
                return []
            data = json.loads(result.stdout or "[]")
            issues = []
            for item in data:
                labels = [l.get("name", "") for l in item.get("labels", [])]
                issues.append(Issue(
                    number=item["number"],
                    title=item.get("title", ""),
                    body=item.get("body", ""),
                    url=item.get("url", ""),
                    labels=labels,
                ))
            return issues
        except Exception:
            return []

    def create_branch(self, issue: Issue) -> str:
        """Create a git branch for the issue."""
        branch_name = f"lidco/issue-{issue.number}"
        try:
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                cwd=self._project_dir,
                capture_output=True,
                check=False,
            )
        except Exception:
            pass
        return branch_name

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
