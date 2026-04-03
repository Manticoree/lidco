"""Context Menu & Quick Actions (Q274)."""
from __future__ import annotations

from lidco.actions.registry import ActionResult, QuickAction, QuickActionRegistry
from lidco.actions.code_provider import CodeAction, CodeActionsProvider
from lidco.actions.file_provider import FileAction, FileActionResult, FileActionsProvider
from lidco.actions.git_provider import GitAction, GitActionResult, GitActionsProvider

__all__ = [
    "ActionResult",
    "CodeAction",
    "CodeActionsProvider",
    "FileAction",
    "FileActionResult",
    "FileActionsProvider",
    "GitAction",
    "GitActionResult",
    "GitActionsProvider",
    "QuickAction",
    "QuickActionRegistry",
]
