"""FileActionsProvider — file operations (simulated)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileAction:
    """A file action specification."""

    action: str  # "create" | "rename" | "move" | "delete" | "copy"
    source: str
    target: str = ""
    template: str = ""


@dataclass(frozen=True)
class FileActionResult:
    """Result of a file action."""

    action: str
    source: str
    target: str
    success: bool
    message: str


class FileActionsProvider:
    """Simulate file operations and keep an action log."""

    def __init__(self) -> None:
        self._log: list[FileActionResult] = []

    def create(self, path: str, content: str = "", template: str = "") -> FileActionResult:
        """Simulate creating *path*."""
        msg = f"Created '{path}'"
        if template:
            msg += f" from template '{template}'"
        result = FileActionResult(
            action="create", source=path, target="", success=True, message=msg,
        )
        self._log.append(result)
        return result

    def rename(self, source: str, target: str) -> FileActionResult:
        """Simulate renaming *source* to *target*."""
        result = FileActionResult(
            action="rename", source=source, target=target,
            success=True, message=f"Renamed '{source}' -> '{target}'",
        )
        self._log.append(result)
        return result

    def move(self, source: str, target: str) -> FileActionResult:
        """Simulate moving *source* to *target*."""
        result = FileActionResult(
            action="move", source=source, target=target,
            success=True, message=f"Moved '{source}' -> '{target}'",
        )
        self._log.append(result)
        return result

    def delete(self, path: str) -> FileActionResult:
        """Simulate deleting *path*."""
        result = FileActionResult(
            action="delete", source=path, target="", success=True,
            message=f"Deleted '{path}'",
        )
        self._log.append(result)
        return result

    def copy(self, source: str, target: str) -> FileActionResult:
        """Simulate copying *source* to *target*."""
        result = FileActionResult(
            action="copy", source=source, target=target,
            success=True, message=f"Copied '{source}' -> '{target}'",
        )
        self._log.append(result)
        return result

    def copy_path(self, path: str) -> str:
        """Return *path* (clipboard simulation)."""
        return path

    def history(self) -> list[FileActionResult]:
        """Return the action log."""
        return list(self._log)

    def undo_last(self) -> FileActionResult | None:
        """Return the inverse of the last action, or ``None``."""
        if not self._log:
            return None
        last = self._log.pop()
        inverse_map = {
            "create": "delete",
            "delete": "create",
            "rename": "rename",
            "move": "move",
            "copy": "delete",
        }
        inv_action = inverse_map.get(last.action, "unknown")
        if last.action in ("rename", "move"):
            return FileActionResult(
                action=inv_action, source=last.target, target=last.source,
                success=True, message=f"Undo: {inv_action} '{last.target}' -> '{last.source}'",
            )
        if last.action == "copy":
            return FileActionResult(
                action=inv_action, source=last.target, target="",
                success=True, message=f"Undo: delete copied '{last.target}'",
            )
        if last.action == "create":
            return FileActionResult(
                action=inv_action, source=last.source, target="",
                success=True, message=f"Undo: delete '{last.source}'",
            )
        # delete -> create (source back)
        return FileActionResult(
            action=inv_action, source=last.source, target="",
            success=True, message=f"Undo: recreate '{last.source}'",
        )

    def summary(self) -> dict:
        """Return a summary dict."""
        return {
            "total_actions": len(self._log),
            "action_types": list({r.action for r in self._log}),
        }
