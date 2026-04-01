"""Tests for context.compression_strategy — StrategyType, CompressionStats, CompressionStrategy."""
from __future__ import annotations

import unittest

from lidco.context.compression_strategy import (
    CompressionStats,
    CompressionStrategy,
    StrategyType,
)


class TestStrategyType(unittest.TestCase):
    def test_values(self):
        self.assertEqual(StrategyType.AGGRESSIVE.value, "aggressive")
        self.assertEqual(StrategyType.BALANCED.value, "balanced")
        self.assertEqual(StrategyType.CONSERVATIVE.value, "conservative")


class TestCompressionStats(unittest.TestCase):
    def test_frozen(self):
        s = CompressionStats(strategy=StrategyType.BALANCED)
        with self.assertRaises(AttributeError):
            s.ratio = 1.0  # type: ignore[misc]

    def test_defaults(self):
        s = CompressionStats(strategy=StrategyType.AGGRESSIVE)
        self.assertEqual(s.original_tokens, 0)
        self.assertEqual(s.compressed_tokens, 0)
        self.assertEqual(s.turns_removed, 0)


class TestCompressionStrategy(unittest.TestCase):
    def _make_messages(self, count: int) -> list[dict]:
        msgs: list[dict] = [{"role": "system", "content": "sys"}]
        for i in range(count):
            role = "user" if i % 2 == 0 else "assistant"
            msgs.append({"role": role, "content": f"Turn {i} content"})
        return msgs

    def test_aggressive_keeps_system_and_last_five(self):
        cs = CompressionStrategy(StrategyType.AGGRESSIVE)
        msgs = self._make_messages(20)
        compressed, stats = cs.compress(msgs)
        non_system = [m for m in compressed if m["role"] != "system"]
        self.assertLessEqual(len(non_system), 5)
        self.assertEqual(stats.strategy, StrategyType.AGGRESSIVE)

    def test_balanced_keeps_system_and_last_ten(self):
        cs = CompressionStrategy(StrategyType.BALANCED)
        msgs = self._make_messages(30)
        compressed, stats = cs.compress(msgs)
        non_system = [m for m in compressed if m["role"] != "system"]
        # 10 recent + 1 summary
        self.assertLessEqual(len(non_system), 11)

    def test_conservative_keeps_more(self):
        cs = CompressionStrategy(StrategyType.CONSERVATIVE)
        msgs = self._make_messages(30)
        compressed, stats = cs.compress(msgs)
        self.assertGreater(len(compressed), 20)

    def test_empty_messages(self):
        cs = CompressionStrategy()
        compressed, stats = cs.compress([])
        self.assertEqual(compressed, [])
        self.assertEqual(stats.turns_removed, 0)

    def test_get_target_ratio(self):
        self.assertAlmostEqual(CompressionStrategy(StrategyType.AGGRESSIVE).get_target_ratio(), 0.3)
        self.assertAlmostEqual(CompressionStrategy(StrategyType.BALANCED).get_target_ratio(), 0.5)
        self.assertAlmostEqual(CompressionStrategy(StrategyType.CONSERVATIVE).get_target_ratio(), 0.7)

    def test_summary_format(self):
        cs = CompressionStrategy()
        stats = CompressionStats(
            strategy=StrategyType.BALANCED,
            original_tokens=100,
            compressed_tokens=50,
            ratio=0.5,
            turns_removed=3,
        )
        s = cs.summary(stats)
        self.assertIn("balanced", s.lower())
        self.assertIn("100", s)
        self.assertIn("50", s)

    def test_small_list_no_change_balanced(self):
        cs = CompressionStrategy(StrategyType.BALANCED)
        msgs = self._make_messages(5)
        compressed, stats = cs.compress(msgs)
        self.assertEqual(len(compressed), len(msgs))

    def test_small_list_no_change_conservative(self):
        cs = CompressionStrategy(StrategyType.CONSERVATIVE)
        msgs = self._make_messages(5)
        compressed, stats = cs.compress(msgs)
        self.assertEqual(len(compressed), len(msgs))

    def test_strategy_property(self):
        cs = CompressionStrategy(StrategyType.AGGRESSIVE)
        self.assertEqual(cs.strategy, StrategyType.AGGRESSIVE)

    def test_ratio_between_zero_and_one(self):
        cs = CompressionStrategy(StrategyType.AGGRESSIVE)
        msgs = self._make_messages(30)
        _, stats = cs.compress(msgs)
        self.assertGreaterEqual(stats.ratio, 0.0)
        self.assertLessEqual(stats.ratio, 1.0)


if __name__ == "__main__":
    unittest.main()
