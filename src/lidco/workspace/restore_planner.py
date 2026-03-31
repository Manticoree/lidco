"""Restore planner for workspace snapshots — Q127."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from lidco.workspace.snapshot2 import WorkspaceSnapshot
from lidco.workspace.file_index import FileIndex


@dataclass
class RestoreAction:
    path: str
    action: str  # "write"/"delete"/"skip"
    reason: str = ""
    content: str = ""


class RestorePlanner:
    """Plan and apply workspace restoration actions."""

    def plan(
        self,
        snapshot: WorkspaceSnapshot,
        current_index: FileIndex,
    ) -> list[RestoreAction]:
        actions: list[RestoreAction] = []
        snap_paths = set(snapshot.files.keys())
        index_paths = set(current_index.list_paths())

        # For each file in snapshot
        for path, fs in snapshot.files.items():
            if current_index.has_changed(path, fs.content):
                actions.append(
                    RestoreAction(path=path, action="write", reason="content differs or not indexed", content=fs.content)
                )
            else:
                actions.append(
                    RestoreAction(path=path, action="skip", reason="unchanged")
                )

        # Files in index but not in snapshot → delete
        for path in index_paths - snap_paths:
            actions.append(
                RestoreAction(path=path, action="delete", reason="not in snapshot")
            )

        return actions

    def apply(
        self,
        actions: list[RestoreAction],
        write_fn: Callable[[str, str], None],
        delete_fn: Callable[[str], None],
    ) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for action in actions:
            if action.action == "skip":
                results[action.path] = True
                continue
            try:
                if action.action == "write":
                    # write_fn needs content — caller passes bound fn
                    write_fn(action.path, action.content)
                elif action.action == "delete":
                    delete_fn(action.path)
                results[action.path] = True
            except Exception:
                results[action.path] = False
        return results
