"""Branch pruner for cleaning up conversation branch trees."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from lidco.conversation.branch_tree import BranchTree


@dataclass(frozen=True)
class PruneResult:
    """Result of a prune operation."""

    removed_count: int
    removed_ids: list[str] = field(default_factory=list)


class BranchPruner:
    """Prune, merge, and archive operations on a :class:`BranchTree`."""

    def __init__(self, tree: BranchTree) -> None:
        self._tree = tree

    # ------------------------------------------------------------------
    # Descendant collection
    # ------------------------------------------------------------------

    def _descendants(self, branch_id: str) -> list[str]:
        """Return all descendant ids of *branch_id* (excluding itself), BFS."""
        result: list[str] = []
        queue: list[str] = [branch_id]
        while queue:
            current = queue.pop(0)
            children = self._tree.get_children(current)
            for child in children:
                result.append(child.id)
                queue.append(child.id)
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def prune(self, branch_id: str) -> PruneResult:
        """Remove *branch_id* and all its descendants.

        Returns a :class:`PruneResult` with the ids that were removed.
        """
        if self._tree.get_branch(branch_id) is None:
            return PruneResult(removed_count=0, removed_ids=[])

        to_remove = self._descendants(branch_id)
        to_remove.append(branch_id)

        removed: list[str] = []
        # Remove deepest first to avoid orphan issues
        for nid in reversed(to_remove):
            if self._tree.remove_branch(nid):
                removed.append(nid)

        return PruneResult(removed_count=len(removed), removed_ids=removed)

    def prune_dead(self, min_messages: int = 0) -> PruneResult:
        """Remove leaf branches with <= *min_messages* messages."""
        removed: list[str] = []
        # Iterate until no more dead leaves to remove
        changed = True
        while changed:
            changed = False
            for leaf in self._tree.leaves():
                if len(leaf.messages) <= min_messages:
                    if self._tree.remove_branch(leaf.id):
                        removed.append(leaf.id)
                        changed = True

        return PruneResult(removed_count=len(removed), removed_ids=removed)

    def merge_back(self, branch_id: str, target_id: str) -> bool:
        """Copy messages from *branch_id* into *target_id*.

        The target node is replaced with a new node containing the
        combined messages.  The source branch is **not** removed.
        Returns ``True`` on success.
        """
        source = self._tree.get_branch(branch_id)
        target = self._tree.get_branch(target_id)
        if source is None or target is None:
            return False

        combined_messages = list(target.messages) + list(source.messages)

        # Remove old target, re-add with combined messages and same id
        # We need direct access to replace the node in-place (id-preserving).
        from lidco.conversation.branch_tree import BranchNode

        new_target = BranchNode(
            id=target.id,
            parent_id=target.parent_id,
            messages=tuple(combined_messages),
            created_at=target.created_at,
            metadata={**target.metadata, "merged_from": branch_id},
        )
        # Replace in the tree's internal store (immutable-style swap)
        self._tree._nodes = {**self._tree._nodes, target.id: new_target}
        return True

    def archive(self, branch_id: str) -> dict:
        """Return serialised data for *branch_id* and its descendants.

        This does **not** remove the branch; call :meth:`prune` afterwards
        if desired.
        """
        node = self._tree.get_branch(branch_id)
        if node is None:
            return {}

        descendant_ids = self._descendants(branch_id)
        all_ids = [branch_id, *descendant_ids]

        archived: dict[str, dict] = {}
        for nid in all_ids:
            n = self._tree.get_branch(nid)
            if n is not None:
                archived[nid] = {
                    "id": n.id,
                    "parent_id": n.parent_id,
                    "messages": list(n.messages),
                    "created_at": n.created_at,
                    "metadata": dict(n.metadata),
                }

        return {"branch_id": branch_id, "nodes": archived}

    def space_savings(self, branch_id: str) -> int:
        """Estimate bytes freed by pruning *branch_id* and descendants."""
        node = self._tree.get_branch(branch_id)
        if node is None:
            return 0

        descendant_ids = self._descendants(branch_id)
        all_ids = [branch_id, *descendant_ids]

        total = 0
        for nid in all_ids:
            n = self._tree.get_branch(nid)
            if n is not None:
                total += len(json.dumps(list(n.messages)))
                total += len(json.dumps(n.metadata))
        return total
