"""Typed hook event definitions (Task 718)."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class InstructionsLoadedEvent:
    """Fired when instruction files are loaded."""

    event_type: ClassVar[str] = "InstructionsLoaded"
    files_loaded: tuple[str, ...] = ()


@dataclass(frozen=True)
class CwdChangedEvent:
    """Fired when current working directory changes."""

    event_type: ClassVar[str] = "CwdChanged"
    old_path: str = ""
    new_path: str = ""


@dataclass(frozen=True)
class FileChangedEvent:
    """Fired when a file is created, modified, or deleted."""

    event_type: ClassVar[str] = "FileChanged"
    path: str = ""
    change_type: str = "modified"


@dataclass(frozen=True)
class TaskCreatedEvent:
    """Fired when a new task is created."""

    event_type: ClassVar[str] = "TaskCreated"
    task_id: str = ""
    task_title: str = ""


@dataclass(frozen=True)
class TaskCompletedEvent:
    """Fired when a task completes."""

    event_type: ClassVar[str] = "TaskCompleted"
    task_id: str = ""
    success: bool = True


@dataclass(frozen=True)
class ElicitationEvent:
    """Fired when elicitation is requested from an MCP server."""

    event_type: ClassVar[str] = "Elicitation"
    server_name: str = ""
    fields: tuple = ()


@dataclass(frozen=True)
class ElicitationResultEvent:
    """Fired when elicitation values are returned."""

    event_type: ClassVar[str] = "ElicitationResult"
    server_name: str = ""
    values: tuple = ()


@dataclass(frozen=True)
class PostCompactEvent:
    """Fired after context compaction."""

    event_type: ClassVar[str] = "PostCompact"
    turns_compacted: int = 0


@dataclass(frozen=True)
class PreCompactEvent:
    """Fired before context compaction."""

    event_type: ClassVar[str] = "PreCompact"
    current_turns: int = 0


@dataclass(frozen=True)
class WorktreeCreateEvent:
    """Fired when a git worktree is created."""

    event_type: ClassVar[str] = "WorktreeCreate"
    path: str = ""
    branch: str = ""


@dataclass(frozen=True)
class WorktreeRemoveEvent:
    """Fired when a git worktree is removed."""

    event_type: ClassVar[str] = "WorktreeRemove"
    path: str = ""


@dataclass(frozen=True)
class UserPromptSubmitEvent:
    """Fired when a user submits a prompt."""

    event_type: ClassVar[str] = "UserPromptSubmit"
    text: str = ""
    session_id: str = ""


def to_hook_event(evt: object) -> "HookEvent":
    """Convert a typed event dataclass to a generic :class:`HookEvent`."""
    from lidco.hooks.event_bus import HookEvent

    return HookEvent(
        event_type=evt.event_type,  # type: ignore[attr-defined]
        payload=dataclasses.asdict(evt),  # type: ignore[arg-type]
    )
