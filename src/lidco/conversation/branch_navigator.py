"""Branch navigator for traversing conversation branch trees."""
from __future__ import annotations

from typing import Optional

from lidco.conversation.branch_tree import BranchNode, BranchTree


class BranchNavigator:
    """Stateful navigator for a :class:`BranchTree`.

    Keeps a *current* pointer and provides movement helpers.
    """

    def __init__(self, tree: BranchTree) -> None:
        self._tree = tree
        self._current_id: Optional[str] = None
        # Auto-set to root if one exists
        root = self._tree.root()
        if root is not None:
            self._current_id = root.id

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current(self) -> BranchNode | None:
        """Return the currently-selected branch node."""
        if self._current_id is None:
            return None
        return self._tree.get_branch(self._current_id)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def jump(self, branch_id: str) -> bool:
        """Jump to *branch_id*. Returns ``True`` on success."""
        node = self._tree.get_branch(branch_id)
        if node is None:
            return False
        self._current_id = branch_id
        return True

    def back(self) -> bool:
        """Move to the parent of the current branch. Returns ``True`` on success."""
        if self._current_id is None:
            return False
        parent = self._tree.get_parent(self._current_id)
        if parent is None:
            return False
        self._current_id = parent.id
        return True

    def forward(self, child_index: int = 0) -> bool:
        """Move to the *child_index*-th child. Returns ``True`` on success."""
        if self._current_id is None:
            return False
        children = self._tree.get_children(self._current_id)
        if child_index < 0 or child_index >= len(children):
            return False
        self._current_id = children[child_index].id
        return True

    def breadcrumb(self) -> list[str]:
        """Return the list of branch ids from root to current."""
        if self._current_id is None:
            return []
        path: list[str] = []
        node = self._tree.get_branch(self._current_id)
        while node is not None:
            path.append(node.id)
            if node.parent_id is None:
                break
            node = self._tree.get_branch(node.parent_id)
        path.reverse()
        return path

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def display_tree(self) -> str:
        """Return an ASCII representation of the branch tree.

        The current branch is marked with ``(*)``.
        """
        root = self._tree.root()
        if root is None:
            return "(empty tree)"
        lines: list[str] = []
        self._render(root, "", True, lines)
        return "\n".join(lines)

    def _render(
        self,
        node: BranchNode,
        prefix: str,
        is_last: bool,
        lines: list[str],
    ) -> None:
        connector = "`-- " if is_last else "|-- "
        marker = "(*)" if node.id == self._current_id else ""
        msg_count = len(node.messages)
        lines.append(f"{prefix}{connector}{node.id} [{msg_count} msg]{marker}")
        children = self._tree.get_children(node.id)
        child_prefix = prefix + ("    " if is_last else "|   ")
        for i, child in enumerate(children):
            self._render(child, child_prefix, i == len(children) - 1, lines)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, keyword: str) -> list[BranchNode]:
        """Return branches whose messages contain *keyword* (case-insensitive)."""
        keyword_lower = keyword.lower()
        results: list[BranchNode] = []
        for node in self._tree.all_branches():
            for msg in node.messages:
                content = str(msg.get("content", ""))
                if keyword_lower in content.lower():
                    results.append(node)
                    break
        return results
