"""Tests for CompletionTrie."""
from __future__ import annotations
import unittest
from lidco.completion.trie import CompletionTrie, TrieNode


class TestTrieNode(unittest.TestCase):
    def test_defaults(self):
        node = TrieNode()
        self.assertEqual(node.children, {})
        self.assertFalse(node.is_end)
        self.assertIsNone(node.value)
        self.assertEqual(node.count, 0)


class TestCompletionTrie(unittest.TestCase):
    def setUp(self):
        self.trie = CompletionTrie()

    # --- insert ---

    def test_insert_single_word(self):
        self.trie.insert("hello")
        self.assertTrue(self.trie.has("hello"))
        self.assertEqual(self.trie.size, 1)

    def test_insert_multiple_words(self):
        self.trie.insert("hello")
        self.trie.insert("help")
        self.trie.insert("world")
        self.assertEqual(self.trie.size, 3)

    def test_insert_with_value(self):
        self.trie.insert("cmd", value=42)
        self.assertTrue(self.trie.has("cmd"))

    def test_insert_empty_string_ignored(self):
        self.trie.insert("")
        self.assertEqual(self.trie.size, 0)

    def test_insert_duplicate_does_not_increase_size(self):
        self.trie.insert("abc")
        self.trie.insert("abc")
        self.assertEqual(self.trie.size, 1)

    def test_insert_duplicate_increments_count(self):
        self.trie.insert("abc")
        self.trie.insert("abc")
        node = self.trie._find_node("abc")
        self.assertEqual(node.count, 2)

    # --- search ---

    def test_search_matching_prefix(self):
        self.trie.insert("apple")
        self.trie.insert("app")
        self.trie.insert("banana")
        results = self.trie.search("app")
        self.assertEqual(results, ["app", "apple"])

    def test_search_no_match(self):
        self.trie.insert("hello")
        self.assertEqual(self.trie.search("xyz"), [])

    def test_search_empty_prefix_returns_all(self):
        self.trie.insert("a")
        self.trie.insert("b")
        results = self.trie.search("")
        self.assertEqual(results, ["a", "b"])

    # --- has ---

    def test_has_missing_word(self):
        self.assertFalse(self.trie.has("nope"))

    def test_has_prefix_only(self):
        self.trie.insert("apple")
        self.assertFalse(self.trie.has("app"))

    # --- delete ---

    def test_delete_existing_word(self):
        self.trie.insert("hello")
        self.assertTrue(self.trie.delete("hello"))
        self.assertFalse(self.trie.has("hello"))
        self.assertEqual(self.trie.size, 0)

    def test_delete_nonexistent_word(self):
        self.assertFalse(self.trie.delete("nope"))

    def test_delete_does_not_affect_sibling(self):
        self.trie.insert("app")
        self.trie.insert("apple")
        self.trie.delete("app")
        self.assertFalse(self.trie.has("app"))
        self.assertTrue(self.trie.has("apple"))

    def test_delete_empty_string(self):
        self.assertFalse(self.trie.delete(""))

    # --- autocomplete ---

    def test_autocomplete_sorted_by_frequency(self):
        self.trie.insert("alpha")
        self.trie.insert("alpha")
        self.trie.insert("alpha")
        self.trie.insert("albedo")
        results = self.trie.autocomplete("al")
        self.assertEqual(results[0], "alpha")

    def test_autocomplete_limit(self):
        for i in range(20):
            self.trie.insert(f"item{i:02d}")
        results = self.trie.autocomplete("item", limit=5)
        self.assertEqual(len(results), 5)

    def test_autocomplete_empty_prefix(self):
        self.trie.insert("a")
        self.trie.insert("b")
        results = self.trie.autocomplete("")
        self.assertGreaterEqual(len(results), 2)

    def test_autocomplete_no_match(self):
        self.trie.insert("hello")
        self.assertEqual(self.trie.autocomplete("xyz"), [])

    # --- words ---

    def test_words_returns_all(self):
        self.trie.insert("cat")
        self.trie.insert("car")
        self.trie.insert("bat")
        self.assertEqual(self.trie.words(), ["bat", "car", "cat"])

    def test_words_empty_trie(self):
        self.assertEqual(self.trie.words(), [])

    # --- increment ---

    def test_increment_existing_word(self):
        self.trie.insert("foo")
        self.trie.increment("foo")
        node = self.trie._find_node("foo")
        self.assertEqual(node.count, 2)

    def test_increment_new_word_inserts(self):
        self.trie.increment("bar")
        self.assertTrue(self.trie.has("bar"))
        self.assertEqual(self.trie.size, 1)

    def test_increment_empty_ignored(self):
        self.trie.increment("")
        self.assertEqual(self.trie.size, 0)


if __name__ == "__main__":
    unittest.main()
