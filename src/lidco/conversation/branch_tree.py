"""Conversation branch tree structure for managing branching conversations."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class BranchNode:
    """Immutable node representing a single conversation branch."""

    id: str
    parent_id: Optional[str]
    messages: tuple[dict, ...]
    created_at: str
    metadata: dict = field(default_factory=dict)


class BranchTree:
    """Tree structure for managing conversation branches.

    All mutations return new state or new ids; internal dicts are
    replaced (not mutated in-place) to preserve snapshot safety.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, BranchNode] = {}
        self._children: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_branch(
        self,
        parent_id: str | None,
        messages: list[dict],
        metadata: dict | None = None,
    ) -> str:
        """Add a new branch under *parent_id* and return its id.

        If *parent_id* is not ``None`` and does not exist in the tree,
        a ``KeyError`` is raised.
        """
        if parent_id is not None and parent_id not in self._nodes:
            raise KeyError(f"Parent branch '{parent_id}' not found")

        branch_id = uuid.uuid4().hex[:8]
        node = BranchNode(
            id=branch_id,
            parent_id=parent_id,
            messages=tuple(messages),
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=dict(metadata) if metadata else {},
        )

        # Immutable-style: build new dicts
        self._nodes = {**self._nodes, branch_id: node}
        parent_key = parent_id if parent_id is not None else "__root__"
        existing_children = list(self._children.get(parent_key, []))
        existing_children.append(branch_id)
        self._children = {**self._children, parent_key: existing_children}

        return branch_id

    def remove_branch(self, branch_id: str) -> bool:
        """Remove a single branch node (not its descendants). Returns True on success."""
        if branch_id not in self._nodes:
            return False

        node = self._nodes[branch_id]
        new_nodes = {k: v for k, v in self._nodes.items() if k != branch_id}

        parent_key = node.parent_id if node.parent_id is not None else "__root__"
        new_children = dict(self._children)
        if parent_key in new_children:
            new_children[parent_key] = [
                c for c in new_children[parent_key] if c != branch_id
            ]

        # Also remove this node's children list entry
        new_children.pop(branch_id, None)

        self._nodes = new_nodes
        self._children = new_children
        return True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_branch(self, branch_id: str) -> BranchNode | None:
        """Return the branch node or ``None``."""
        return self._nodes.get(branch_id)

    def get_children(self, branch_id: str) -> list[BranchNode]:
        """Return direct children of the given branch."""
        child_ids = self._children.get(branch_id, [])
        return [self._nodes[cid] for cid in child_ids if cid in self._nodes]

    def get_parent(self, branch_id: str) -> BranchNode | None:
        """Return the parent node or ``None``."""
        node = self._nodes.get(branch_id)
        if node is None or node.parent_id is None:
            return None
        return self._nodes.get(node.parent_id)

    def depth(self, branch_id: str) -> int:
        """Return depth of the branch (root = 0). -1 if not found."""
        node = self._nodes.get(branch_id)
        if node is None:
            return -1
        d = 0
        current = node
        while current.parent_id is not None:
            parent = self._nodes.get(current.parent_id)
            if parent is None:
                break
            d += 1
            current = parent
        return d

    def leaves(self) -> list[BranchNode]:
        """Return all leaf nodes (nodes with no children)."""
        nodes_with_children: set[str] = set()
        for children in self._children.values():
            for cid in children:
                # cid is a child -> its parent has children
                pass
        # A node is a leaf if it has no entry in _children or the list is empty
        parent_ids: set[str] = set()
        for child_list in self._children.values():
            for cid in child_list:
                node = self._nodes.get(cid)
                if node and node.parent_id is not None:
                    parent_ids.add(node.parent_id)
                elif node and node.parent_id is None:
                    parent_ids.add("__root__")

        # Simpler: a node is a leaf if its id is not a key in _children
        # OR its key maps to an empty list
        result: list[BranchNode] = []
        for nid, node in self._nodes.items():
            children = self._children.get(nid, [])
            if not children:
                result.append(node)
        return result

    def root(self) -> BranchNode | None:
        """Return the root node (a node with parent_id=None), or None."""
        root_ids = self._children.get("__root__", [])
        if root_ids:
            return self._nodes.get(root_ids[0])
        # Fallback: find any node with parent_id=None
        for node in self._nodes.values():
            if node.parent_id is None:
                return node
        return None

    def all_branches(self) -> list[BranchNode]:
        """Return all nodes in the tree."""
        return list(self._nodes.values())

    def to_dict(self) -> dict:
        """Return a JSON-serializable representation of the tree."""
        return {
            "nodes": {
                nid: {
                    "id": n.id,
                    "parent_id": n.parent_id,
                    "messages": list(n.messages),
                    "created_at": n.created_at,
                    "metadata": dict(n.metadata),
                }
                for nid, n in self._nodes.items()
            },
            "children": {k: list(v) for k, v in self._children.items()},
        }
