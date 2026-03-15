"""File writing tool."""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult

if TYPE_CHECKING:
    from lidco.core.sandbox import SandboxValidator

# Maximum diff lines shown in the confirmation panel.
_MAX_DIFF_LINES = 40


class FileWriteTool(BaseTool):
    """Write content to a file (creates or overwrites)."""

    # Injected by the CLI layer to ask the user before overwriting.
    # Signature: async (path: str, old: str, new: str) -> bool
    _confirm_callback: Callable[[str, str, str], Awaitable[bool]] | None = None
    _sandbox: SandboxValidator | None = None
    # Task 283: checkpoint callback — (path: str, old_content: str | None) -> None
    _checkpoint_callback: Callable[[str, "str | None"], None] | None = None

    def set_sandbox(self, sandbox: SandboxValidator) -> None:
        self._sandbox = sandbox

    def set_checkpoint_callback(
        self, callback: Callable[[str, "str | None"], None] | None
    ) -> None:
        """Set a callback invoked with (path, old_content) before every write.

        Called for both new files (old_content=None) and overwrites.
        Used by CheckpointManager to record undo snapshots.
        """
        self._checkpoint_callback = callback

    def set_confirm_callback(
        self,
        callback: Callable[[str, str, str], Awaitable[bool]] | None,
    ) -> None:
        """Set an async callback invoked when overwriting an existing file.

        The callback receives (path, old_content, new_content) and must return
        True to proceed with the write, False to cancel.
        """
        self._confirm_callback = callback

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "Write/create file (overwrites existing)."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="Path to the file to write.",
            ),
            ToolParameter(
                name="content",
                type="string",
                description="The content to write to the file.",
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.ASK

    @staticmethod
    def build_diff(old: str, new: str, path: str) -> str:
        """Return a unified diff string (at most _MAX_DIFF_LINES lines)."""
        old_lines = old.splitlines()
        new_lines = new.splitlines()
        diff_lines = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        ))
        if not diff_lines:
            return ""
        if len(diff_lines) > _MAX_DIFF_LINES:
            orig_count = len(diff_lines)
            diff_lines = diff_lines[:_MAX_DIFF_LINES]
            diff_lines.append(f"... (showing {_MAX_DIFF_LINES} of {orig_count} lines)")
        return "\n".join(diff_lines)

    async def _run(self, **kwargs: Any) -> ToolResult:
        path = Path(kwargs["path"]).resolve()
        content: str = kwargs["content"]

        # Sandbox validation
        if self._sandbox is not None:
            allowed, reason = self._sandbox.validate_write_path(str(path))
            if not allowed:
                return ToolResult(
                    output="", success=False, error=f"Sandbox blocked: {reason}"
                )

        # Task 283: record checkpoint before write
        if self._checkpoint_callback is not None:
            try:
                old_for_cp = path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
                self._checkpoint_callback(str(path), old_for_cp)
            except Exception:
                pass

        # Confirm before overwriting an existing file
        if path.exists() and self._confirm_callback is not None:
            try:
                old_content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                old_content = ""
            proceed = await self._confirm_callback(str(path), old_content, content)
            if not proceed:
                return ToolResult(
                    output=f"Write cancelled by user: {path}",
                    success=True,
                    metadata={"path": str(path), "cancelled": True},
                )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        return ToolResult(
            output=f"Successfully wrote {len(content)} bytes to {path}",
            metadata={"path": str(path), "bytes": len(content)},
        )
