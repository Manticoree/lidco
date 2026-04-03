"""Branch comparator for diffing and comparing conversation branches."""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from lidco.conversation.branch_tree import BranchTree


@dataclass(frozen=True)
class BranchDiff:
    """Result of comparing two branches."""

    divergence_point: str | None
    unique_a: list[dict] = field(default_factory=list)
    unique_b: list[dict] = field(default_factory=list)
    common: list[dict] = field(default_factory=list)


class BranchComparator:
    """Compare and diff conversation branches within a :class:`BranchTree`."""

    def __init__(self, tree: BranchTree) -> None:
        self._tree = tree

    # ------------------------------------------------------------------
    # Ancestry helpers
    # ------------------------------------------------------------------

    def _ancestors(self, branch_id: str) -> list[str]:
        """Return list of ids from root to *branch_id* (inclusive)."""
        path: list[str] = []
        current = self._tree.get_branch(branch_id)
        while current is not None:
            path.append(current.id)
            if current.parent_id is None:
                break
            current = self._tree.get_branch(current.parent_id)
        path.reverse()
        return path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_divergence(self, branch_a: str, branch_b: str) -> str | None:
        """Return the common ancestor id of *branch_a* and *branch_b*.

        Returns ``None`` if they share no common ancestor.
        """
        ancestors_a = self._ancestors(branch_a)
        ancestors_b_set = set(self._ancestors(branch_b))
        common: str | None = None
        for aid in ancestors_a:
            if aid in ancestors_b_set:
                common = aid
        return common

    def diff(self, branch_a: str, branch_b: str) -> BranchDiff:
        """Compute the diff between two branches.

        Messages on the path from root to the divergence point are
        considered *common*.  Messages on branches beyond the
        divergence point are *unique_a* / *unique_b*.
        """
        node_a = self._tree.get_branch(branch_a)
        node_b = self._tree.get_branch(branch_b)
        if node_a is None or node_b is None:
            return BranchDiff(divergence_point=None)

        divergence = self.find_divergence(branch_a, branch_b)

        # Collect messages from divergence point ancestors (common)
        common_msgs: list[dict] = []
        if divergence is not None:
            for nid in self._ancestors(branch_a):
                node = self._tree.get_branch(nid)
                if node is not None:
                    common_msgs.extend(node.messages)
                if nid == divergence:
                    break

        # Unique messages: messages on path from divergence to each branch
        # (excluding divergence itself)
        unique_a = self._messages_after(branch_a, divergence)
        unique_b = self._messages_after(branch_b, divergence)

        return BranchDiff(
            divergence_point=divergence,
            unique_a=unique_a,
            unique_b=unique_b,
            common=common_msgs,
        )

    def cost_comparison(self, branch_a: str, branch_b: str) -> dict:
        """Return message counts and content lengths for both branches."""
        node_a = self._tree.get_branch(branch_a)
        node_b = self._tree.get_branch(branch_b)

        msgs_a: tuple[dict, ...] = node_a.messages if node_a else ()
        msgs_b: tuple[dict, ...] = node_b.messages if node_b else ()

        return {
            "message_count_a": len(msgs_a),
            "message_count_b": len(msgs_b),
            "content_length_a": sum(
                len(str(m.get("content", ""))) for m in msgs_a
            ),
            "content_length_b": sum(
                len(str(m.get("content", ""))) for m in msgs_b
            ),
        }

    def similarity(self, branch_a: str, branch_b: str) -> float:
        """Return similarity ratio (0.0 - 1.0) based on common messages.

        Uses JSON serialisation to compare messages structurally.
        """
        node_a = self._tree.get_branch(branch_a)
        node_b = self._tree.get_branch(branch_b)
        if node_a is None or node_b is None:
            return 0.0

        set_a = {json.dumps(m, sort_keys=True) for m in node_a.messages}
        set_b = {json.dumps(m, sort_keys=True) for m in node_b.messages}

        if not set_a and not set_b:
            return 1.0

        union = set_a | set_b
        intersection = set_a & set_b
        return len(intersection) / len(union) if union else 1.0

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _messages_after(
        self, branch_id: str, divergence_id: str | None
    ) -> list[dict]:
        """Collect messages on the path from *divergence_id* to *branch_id*,
        excluding messages at *divergence_id* itself."""
        path = self._ancestors(branch_id)
        collecting = divergence_id is None
        msgs: list[dict] = []
        for nid in path:
            if nid == divergence_id:
                collecting = True
                continue
            if collecting:
                node = self._tree.get_branch(nid)
                if node is not None:
                    msgs.extend(node.messages)
        return msgs
