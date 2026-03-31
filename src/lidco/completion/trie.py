"""Trie-based prefix matching for autocompletion."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrieNode:
    """A node in the completion trie."""

    children: dict[str, TrieNode] = field(default_factory=dict)
    is_end: bool = False
    value: Any = None
    count: int = 0


class CompletionTrie:
    """Trie data structure for prefix-based autocompletion."""

    def __init__(self) -> None:
        self._root = TrieNode()
        self._size = 0

    def insert(self, word: str, value: Any = None) -> None:
        """Insert *word* into the trie with an optional associated *value*."""
        if not word:
            return
        node = self._root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        if not node.is_end:
            self._size += 1
        node.is_end = True
        node.value = value
        node.count += 1

    def search(self, prefix: str) -> list[str]:
        """Return all words that start with *prefix*."""
        node = self._find_node(prefix)
        if node is None:
            return []
        results: list[str] = []
        self._collect(node, prefix, results)
        return sorted(results)

    def has(self, word: str) -> bool:
        """Return ``True`` if *word* is an exact match in the trie."""
        node = self._find_node(word)
        return node is not None and node.is_end

    def delete(self, word: str) -> bool:
        """Remove *word* from the trie.  Returns ``True`` if it existed."""
        if not word:
            return False
        return self._delete(self._root, word, 0)

    def autocomplete(self, prefix: str, limit: int = 10) -> list[str]:
        """Return top completions for *prefix* sorted by descending frequency."""
        node = self._find_node(prefix)
        if node is None:
            return []
        items: list[tuple[str, int]] = []
        self._collect_with_count(node, prefix, items)
        items.sort(key=lambda t: (-t[1], t[0]))
        return [w for w, _ in items[:limit]]

    @property
    def size(self) -> int:
        """Total number of words stored."""
        return self._size

    def words(self) -> list[str]:
        """Return all words in the trie."""
        results: list[str] = []
        self._collect(self._root, "", results)
        return sorted(results)

    def increment(self, word: str) -> None:
        """Increase the usage count for *word* (inserts if absent)."""
        if not word:
            return
        node = self._root
        for ch in word:
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        if not node.is_end:
            self._size += 1
            node.is_end = True
        node.count += 1

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_node(self, prefix: str) -> TrieNode | None:
        node = self._root
        for ch in prefix:
            if ch not in node.children:
                return None
            node = node.children[ch]
        return node

    def _collect(self, node: TrieNode, prefix: str, results: list[str]) -> None:
        if node.is_end:
            results.append(prefix)
        for ch in sorted(node.children):
            self._collect(node.children[ch], prefix + ch, results)

    def _collect_with_count(
        self, node: TrieNode, prefix: str, items: list[tuple[str, int]]
    ) -> None:
        if node.is_end:
            items.append((prefix, node.count))
        for ch in sorted(node.children):
            self._collect_with_count(node.children[ch], prefix + ch, items)

    def _delete(self, node: TrieNode, word: str, depth: int) -> bool:
        if depth == len(word):
            if not node.is_end:
                return False
            node.is_end = False
            node.value = None
            node.count = 0
            self._size -= 1
            return len(node.children) == 0
        ch = word[depth]
        child = node.children.get(ch)
        if child is None:
            return False
        should_remove = self._delete(child, word, depth + 1)
        if should_remove:
            del node.children[ch]
            return not node.is_end and len(node.children) == 0
        return False
