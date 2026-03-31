"""Read-only plan mode -- analyze without modifying files -- Q162."""
from __future__ import annotations

from dataclasses import dataclass, field


_BLOCKED_OPERATIONS: frozenset[str] = frozenset(
    {
        "file_write",
        "file_delete",
        "bash_execute",
        "git_push",
        "git_commit",
    }
)

_ALLOWED_OPERATIONS: frozenset[str] = frozenset(
    {
        "file_read",
        "grep",
        "glob",
        "git_status",
        "git_diff",
        "git_log",
    }
)


@dataclass
class PlanModeState:
    """Snapshot of plan-mode state."""

    active: bool = False
    blocked_operations: list[str] = field(default_factory=lambda: sorted(_BLOCKED_OPERATIONS))
    plan_output: list[str] = field(default_factory=list)


class PlanMode:
    """Read-only planning mode that blocks mutating operations.

    When active, operations such as file writes, deletes, bash execution,
    and git pushes / commits are rejected.  Read-only operations like file
    reads, grep, glob and git inspection commands remain allowed.

    Plan lines are accumulated so the user can review the proposed plan as
    a markdown document.
    """

    def __init__(self) -> None:
        self._active: bool = False
        self._plan_lines: list[str] = []

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """Enter plan mode (read-only)."""
        self._active = True

    def deactivate(self) -> None:
        """Leave plan mode (allow mutations again)."""
        self._active = False

    @property
    def is_active(self) -> bool:
        """Whether plan mode is currently active."""
        return self._active

    # ------------------------------------------------------------------
    # Operation gating
    # ------------------------------------------------------------------

    def check_operation(self, op_type: str) -> bool:
        """Return ``True`` if *op_type* is allowed, ``False`` if blocked.

        When plan mode is **inactive** every operation is allowed.
        When **active**, only operations in the allow-list pass; everything
        else (especially the explicit block-list) is rejected.
        """
        if not self._active:
            return True
        if op_type in _ALLOWED_OPERATIONS:
            return True
        return False

    # ------------------------------------------------------------------
    # Plan accumulation
    # ------------------------------------------------------------------

    def add_plan_line(self, line: str) -> None:
        """Append a line to the accumulated plan output."""
        self._plan_lines.append(line)

    def get_plan(self) -> str:
        """Return the accumulated plan as a markdown string."""
        return "\n".join(self._plan_lines)

    def clear(self) -> None:
        """Clear accumulated plan output."""
        self._plan_lines.clear()

    # ------------------------------------------------------------------
    # State snapshot
    # ------------------------------------------------------------------

    def state(self) -> PlanModeState:
        """Return a snapshot of current plan-mode state."""
        return PlanModeState(
            active=self._active,
            blocked_operations=sorted(_BLOCKED_OPERATIONS),
            plan_output=list(self._plan_lines),
        )
