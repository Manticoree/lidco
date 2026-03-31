"""Detect git operations and refresh context accordingly."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import time


@dataclass
class GitEvent:
    event_type: str  # "branch_switch", "pull", "merge", "rebase", "stash_pop", "commit", "reset"
    details: str
    detected_at: float = field(default_factory=time.time)
    branch_before: str | None = None
    branch_after: str | None = None


@dataclass
class GitState:
    branch: str
    head_commit: str
    is_merging: bool = False
    is_rebasing: bool = False
    stash_count: int = 0


class GitEventListener:
    def __init__(self, repo_dir: str):
        self._repo_dir = repo_dir
        self._last_state: GitState | None = None
        self._events: list[GitEvent] = []
        self._callbacks: list = []

    @property
    def repo_dir(self) -> str:
        return self._repo_dir

    @property
    def events(self) -> list[GitEvent]:
        return list(self._events)

    def on_event(self, callback) -> None:
        """Register callback for git events."""
        self._callbacks = [*self._callbacks, callback]

    def get_current_state(self) -> GitState:
        """Get current git state by reading .git directory."""
        git_dir = os.path.join(self._repo_dir, ".git")

        branch = "unknown"
        head_commit = "unknown"
        is_merging = False
        is_rebasing = False
        stash_count = 0

        # Read HEAD for branch
        head_file = os.path.join(git_dir, "HEAD")
        if os.path.isfile(head_file):
            try:
                with open(head_file, "r") as f:
                    content = f.read().strip()
                if content.startswith("ref: refs/heads/"):
                    branch = content[16:]
                else:
                    head_commit = content[:8]
                    branch = f"detached:{head_commit}"
            except OSError:
                pass

        # Check for merge state
        if os.path.exists(os.path.join(git_dir, "MERGE_HEAD")):
            is_merging = True

        # Check for rebase state
        if os.path.isdir(os.path.join(git_dir, "rebase-merge")) or os.path.isdir(
            os.path.join(git_dir, "rebase-apply")
        ):
            is_rebasing = True

        # Count stashes
        stash_file = os.path.join(git_dir, "refs", "stash")
        if os.path.isfile(stash_file):
            stash_count = 1  # simplified: just check existence

        # Read HEAD commit from branch ref
        refs_path = os.path.join(git_dir, "refs", "heads", branch)
        if os.path.isfile(refs_path):
            try:
                with open(refs_path, "r") as f:
                    head_commit = f.read().strip()[:8]
            except OSError:
                pass

        return GitState(
            branch=branch,
            head_commit=head_commit,
            is_merging=is_merging,
            is_rebasing=is_rebasing,
            stash_count=stash_count,
        )

    def poll(self) -> list[GitEvent]:
        """Poll for git state changes. Returns new events since last poll."""
        current = self.get_current_state()
        events: list[GitEvent] = []

        if self._last_state is not None:
            prev = self._last_state

            if current.branch != prev.branch:
                events.append(GitEvent(
                    event_type="branch_switch",
                    details=f"Switched from {prev.branch} to {current.branch}",
                    branch_before=prev.branch,
                    branch_after=current.branch,
                ))

            if current.head_commit != prev.head_commit and current.branch == prev.branch:
                events.append(GitEvent(
                    event_type="commit",
                    details=f"New commit: {current.head_commit}",
                ))

            if current.is_merging and not prev.is_merging:
                events.append(GitEvent(
                    event_type="merge",
                    details="Merge in progress",
                ))

            if current.is_rebasing and not prev.is_rebasing:
                events.append(GitEvent(
                    event_type="rebase",
                    details="Rebase in progress",
                ))

            if current.stash_count < prev.stash_count:
                events.append(GitEvent(
                    event_type="stash_pop",
                    details="Stash popped",
                ))

        self._last_state = current
        self._events = [*self._events, *events]

        # Notify callbacks
        for event in events:
            for cb in self._callbacks:
                try:
                    cb(event)
                except Exception:
                    pass

        return events

    def clear_events(self) -> None:
        """Clear event history."""
        self._events = []

    def format_state(self, state: GitState | None = None) -> str:
        """Format git state as readable string."""
        s = state or self._last_state
        if not s:
            return "Git state: unknown (not polled yet)"
        parts = [f"Branch: {s.branch}", f"HEAD: {s.head_commit}"]
        if s.is_merging:
            parts.append("MERGING")
        if s.is_rebasing:
            parts.append("REBASING")
        if s.stash_count > 0:
            parts.append(f"Stashes: {s.stash_count}")
        return " | ".join(parts)
