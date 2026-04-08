"""Retrospective — generate retrospectives from session data with action items."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class RetroItem:
    """A single retrospective item."""

    category: str  # "well", "improve", "action"
    text: str
    author: str = ""
    votes: int = 0

    def with_votes(self, votes: int) -> RetroItem:
        """Return item with updated votes."""
        return RetroItem(
            category=self.category,
            text=self.text,
            author=self.author,
            votes=votes,
        )


@dataclass(frozen=True)
class ActionItem:
    """An action item from retrospective."""

    description: str
    assignee: str = ""
    due_date: Optional[datetime.date] = None
    completed: bool = False

    def mark_complete(self) -> ActionItem:
        """Return completed action item."""
        return ActionItem(
            description=self.description,
            assignee=self.assignee,
            due_date=self.due_date,
            completed=True,
        )


@dataclass(frozen=True)
class SessionSummary:
    """Summary of a development session for retro input."""

    session_id: str
    start: datetime.datetime
    end: datetime.datetime
    commands_run: int = 0
    files_modified: int = 0
    errors_encountered: int = 0
    commits_made: int = 0
    description: str = ""


@dataclass
class Retrospective:
    """A retrospective document."""

    title: str
    date: datetime.date
    items: List[RetroItem] = field(default_factory=list)
    action_items: List[ActionItem] = field(default_factory=list)
    sessions: List[SessionSummary] = field(default_factory=list)

    @property
    def went_well(self) -> List[RetroItem]:
        """Items that went well."""
        return [i for i in self.items if i.category == "well"]

    @property
    def needs_improvement(self) -> List[RetroItem]:
        """Items that need improvement."""
        return [i for i in self.items if i.category == "improve"]

    def format(self) -> str:
        """Format retrospective as readable text."""
        lines = [f"Retrospective: {self.title}", f"Date: {self.date.isoformat()}", ""]

        if self.sessions:
            total_cmds = sum(s.commands_run for s in self.sessions)
            total_files = sum(s.files_modified for s in self.sessions)
            total_errors = sum(s.errors_encountered for s in self.sessions)
            total_commits = sum(s.commits_made for s in self.sessions)
            lines.append(f"Sessions: {len(self.sessions)}")
            lines.append(
                f"Stats: {total_cmds} commands, {total_files} files modified, "
                f"{total_errors} errors, {total_commits} commits"
            )
            lines.append("")

        well = self.went_well
        lines.append("What went well:")
        if well:
            for item in sorted(well, key=lambda i: i.votes, reverse=True):
                vote_str = f" (+{item.votes})" if item.votes > 0 else ""
                lines.append(f"  + {item.text}{vote_str}")
        else:
            lines.append("  (no items)")

        lines.append("")
        improve = self.needs_improvement
        lines.append("What needs improvement:")
        if improve:
            for item in sorted(improve, key=lambda i: i.votes, reverse=True):
                vote_str = f" (+{item.votes})" if item.votes > 0 else ""
                lines.append(f"  - {item.text}{vote_str}")
        else:
            lines.append("  (no items)")

        if self.action_items:
            lines.append("")
            lines.append("Action items:")
            for ai in self.action_items:
                status = "[x]" if ai.completed else "[ ]"
                assignee = f" @{ai.assignee}" if ai.assignee else ""
                due = f" (due {ai.due_date.isoformat()})" if ai.due_date else ""
                lines.append(f"  {status} {ai.description}{assignee}{due}")

        return "\n".join(lines)


class RetroGenerator:
    """Generate retrospectives from session data."""

    def __init__(self) -> None:
        self._sessions: List[SessionSummary] = []
        self._items: List[RetroItem] = []
        self._actions: List[ActionItem] = []

    def add_session(self, session: SessionSummary) -> None:
        """Add session data for the retrospective."""
        self._sessions.append(session)

    def add_item(self, category: str, text: str, author: str = "") -> RetroItem:
        """Add a retro item (well/improve/action)."""
        if category not in ("well", "improve", "action"):
            raise ValueError(f"Invalid category: {category}. Use well/improve/action.")
        item = RetroItem(category=category, text=text, author=author)
        self._items.append(item)
        return item

    def add_action(
        self,
        description: str,
        assignee: str = "",
        due_date: Optional[datetime.date] = None,
    ) -> ActionItem:
        """Add an action item."""
        action = ActionItem(description=description, assignee=assignee, due_date=due_date)
        self._actions.append(action)
        return action

    def vote(self, index: int) -> Optional[RetroItem]:
        """Upvote an item by index."""
        if 0 <= index < len(self._items):
            old = self._items[index]
            updated = old.with_votes(old.votes + 1)
            self._items[index] = updated
            return updated
        return None

    def generate(
        self,
        title: str = "Sprint Retrospective",
        date: Optional[datetime.date] = None,
    ) -> Retrospective:
        """Generate a retrospective from collected data."""
        target_date = date or datetime.date.today()

        # Auto-generate items from session data if no manual items
        items = list(self._items)
        if not items and self._sessions:
            items = self._auto_generate_items()

        return Retrospective(
            title=title,
            date=target_date,
            items=items,
            action_items=list(self._actions),
            sessions=list(self._sessions),
        )

    def _auto_generate_items(self) -> List[RetroItem]:
        """Auto-generate retro items from session data."""
        items: List[RetroItem] = []
        total_errors = sum(s.errors_encountered for s in self._sessions)
        total_commits = sum(s.commits_made for s in self._sessions)
        total_files = sum(s.files_modified for s in self._sessions)

        if total_commits > 0:
            items.append(RetroItem(
                category="well",
                text=f"Made {total_commits} commits across {len(self._sessions)} sessions",
            ))

        if total_files > 10:
            items.append(RetroItem(
                category="well",
                text=f"Modified {total_files} files — good productivity",
            ))

        if total_errors > 5:
            items.append(RetroItem(
                category="improve",
                text=f"Encountered {total_errors} errors — consider better error handling",
            ))

        if total_errors == 0 and total_commits > 0:
            items.append(RetroItem(
                category="well",
                text="Zero errors encountered — clean sessions",
            ))

        return items

    def clear(self) -> None:
        """Clear all collected data."""
        self._sessions.clear()
        self._items.clear()
        self._actions.clear()
