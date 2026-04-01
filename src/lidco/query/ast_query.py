"""XPath-like AST queries with pattern matching."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class ASTQueryError(Exception):
    """Raised on AST query failures."""


@dataclass
class ASTNode:
    """A node in an abstract syntax tree."""

    type: str
    name: str = ""
    children: list["ASTNode"] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    line: int = 0


@dataclass(frozen=True)
class ASTPattern:
    """Pattern for matching AST nodes."""

    node_type: str | None = None
    name_pattern: str | None = None
    has_children: bool | None = None
    min_children: int | None = None
    attribute_match: dict[str, Any] = field(default_factory=dict)


def _matches(node: ASTNode, pattern: ASTPattern) -> bool:
    """Return True if *node* matches *pattern*."""
    if pattern.node_type is not None and node.type != pattern.node_type:
        return False
    if pattern.name_pattern is not None:
        if not re.fullmatch(pattern.name_pattern, node.name):
            return False
    if pattern.has_children is not None:
        if pattern.has_children != bool(node.children):
            return False
    if pattern.min_children is not None:
        if len(node.children) < pattern.min_children:
            return False
    for key, val in pattern.attribute_match.items():
        if node.attributes.get(key) != val:
            return False
    return True


class ASTQueryEngine:
    """Query engine for AST trees."""

    def find(self, root: ASTNode, pattern: ASTPattern) -> list[ASTNode]:
        """Find all nodes matching *pattern* via recursive DFS."""
        results: list[ASTNode] = []
        self._dfs(root, pattern, results)
        return results

    def _dfs(self, node: ASTNode, pattern: ASTPattern, acc: list[ASTNode]) -> None:
        if _matches(node, pattern):
            acc.append(node)
        for child in node.children:
            self._dfs(child, pattern, acc)

    def find_by_type(self, root: ASTNode, node_type: str) -> list[ASTNode]:
        """Find all nodes of the given *node_type*."""
        return self.find(root, ASTPattern(node_type=node_type))

    def find_by_name(self, root: ASTNode, name_pattern: str) -> list[ASTNode]:
        """Find all nodes whose name matches *name_pattern* (regex)."""
        return self.find(root, ASTPattern(name_pattern=name_pattern))

    def ancestors(self, root: ASTNode, target: ASTNode) -> list[ASTNode]:
        """Return the path from *root* to *target* (inclusive)."""
        path: list[ASTNode] = []
        if self._find_path(root, target, path):
            return path
        return []

    def _find_path(self, node: ASTNode, target: ASTNode, path: list[ASTNode]) -> bool:
        path.append(node)
        if node is target:
            return True
        for child in node.children:
            if self._find_path(child, target, path):
                return True
        path.pop()
        return False

    def depth(self, root: ASTNode) -> int:
        """Return the maximum depth of the tree rooted at *root*."""
        if not root.children:
            return 1
        return 1 + max(self.depth(c) for c in root.children)
