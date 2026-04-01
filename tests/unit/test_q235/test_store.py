"""Tests for thinkback.store."""
from __future__ import annotations

import unittest

from lidco.thinkback.store import ThinkingBlock, ThinkingStore


class TestThinkingBlock(unittest.TestCase):
    def test_frozen(self) -> None:
        block = ThinkingBlock(turn=1, content="hello")
        with self.assertRaises(AttributeError):
            block.turn = 2  # type: ignore[misc]

    def test_defaults(self) -> None:
        block = ThinkingBlock(turn=0, content="")
        self.assertEqual(block.token_count, 0)
        self.assertEqual(block.model, "")
        self.assertIsInstance(block.timestamp, float)


class TestThinkingStore(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ThinkingStore()

    def test_append_returns_block(self) -> None:
        block = self.store.append(1, "thinking text")
        self.assertIsInstance(block, ThinkingBlock)
        self.assertEqual(block.turn, 1)
        self.assertEqual(block.content, "thinking text")

    def test_append_auto_token_count(self) -> None:
        block = self.store.append(1, "a" * 100)
        self.assertEqual(block.token_count, 25)

    def test_append_with_model(self) -> None:
        block = self.store.append(1, "text", model="claude-4")
        self.assertEqual(block.model, "claude-4")

    def test_get_by_turn(self) -> None:
        self.store.append(1, "first")
        self.store.append(2, "second")
        self.store.append(1, "third")
        result = self.store.get_by_turn(1)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(b.turn == 1 for b in result))

    def test_get_by_turn_empty(self) -> None:
        self.assertEqual(self.store.get_by_turn(99), [])

    def test_get_all(self) -> None:
        self.store.append(1, "a")
        self.store.append(2, "b")
        self.assertEqual(len(self.store.get_all()), 2)

    def test_get_latest(self) -> None:
        for i in range(10):
            self.store.append(i, f"block {i}")
        latest = self.store.get_latest(3)
        self.assertEqual(len(latest), 3)
        self.assertEqual(latest[0].turn, 7)

    def test_total_tokens(self) -> None:
        self.store.append(1, "a" * 40)  # 10 tokens
        self.store.append(2, "b" * 80)  # 20 tokens
        self.assertEqual(self.store.total_tokens(), 30)

    def test_turn_count(self) -> None:
        self.store.append(1, "a")
        self.store.append(1, "b")
        self.store.append(2, "c")
        self.assertEqual(self.store.turn_count(), 2)

    def test_clear(self) -> None:
        self.store.append(1, "a")
        self.store.clear()
        self.assertEqual(len(self.store.get_all()), 0)
        self.assertEqual(self.store.total_tokens(), 0)

    def test_summary(self) -> None:
        self.store.append(1, "hello world test")
        summary = self.store.summary()
        self.assertIn("1 blocks", summary)
        self.assertIn("1 turns", summary)


if __name__ == "__main__":
    unittest.main()
