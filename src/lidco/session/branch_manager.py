"""Session Branch Manager — create, switch, list, delete conversation branches (Q165/Task 937)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Branch:
    """A conversation branch with its own history and file state."""

    branch_id: str
    name: str
    parent_id: str | None
    created_at: float
    conversation: list[dict]
    file_snapshots: dict[str, str]
    is_active: bool = False


class BranchManager:
    """Manage conversation branches (fork / switch / list / delete)."""

    def __init__(self, max_branches: int = 20) -> None:
        self._max_branches = max_branches
        self._branches: dict[str, Branch] = {}
        self._active_id: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        conversation: list[dict],
        files: dict[str, str],
        parent_id: str | None = None,
    ) -> Branch:
        """Create a new branch.  Raises ``ValueError`` if limit exceeded."""
        if len(self._branches) >= self._max_branches:
            raise ValueError(
                f"Branch limit reached ({self._max_branches}). "
                "Delete an existing branch first."
            )
        branch_id = uuid.uuid4().hex[:12]
        branch = Branch(
            branch_id=branch_id,
            name=name,
            parent_id=parent_id,
            created_at=time.time(),
            conversation=list(conversation),
            file_snapshots=dict(files),
            is_active=False,
        )
        self._branches[branch_id] = branch
        return branch

    def switch(self, branch_id: str) -> Branch:
        """Activate *branch_id*.  Raises ``KeyError`` if not found."""
        if branch_id not in self._branches:
            raise KeyError(f"Branch '{branch_id}' not found.")
        # Deactivate current
        if self._active_id and self._active_id in self._branches:
            self._branches[self._active_id].is_active = False
        self._branches[branch_id].is_active = True
        self._active_id = branch_id
        return self._branches[branch_id]

    def get_active(self) -> Branch | None:
        """Return the currently active branch, or ``None``."""
        if self._active_id is None:
            return None
        return self._branches.get(self._active_id)

    def list_branches(self) -> list[Branch]:
        """Return all branches sorted by creation time."""
        return sorted(self._branches.values(), key=lambda b: b.created_at)

    def delete(self, branch_id: str) -> bool:
        """Delete a branch.  Returns ``True`` on success, ``False`` if missing."""
        if branch_id not in self._branches:
            return False
        if self._active_id == branch_id:
            self._active_id = None
        del self._branches[branch_id]
        return True

    def get(self, branch_id: str) -> Branch | None:
        """Look up a branch by id."""
        return self._branches.get(branch_id)
