"""Tests for ConversationProfiler (Q244)."""
from __future__ import annotations

import unittest

from lidco.conversation.profiler import ConversationProfiler


def _msgs(contents: list[str], role: str = "user") -> list[dict]:
    return [{"role": role, "content": c} for c in contents]


class TestCostPerTurn(unittest.TestCase):
    def test_cumulative_tokens(self):
        profiler = ConversationProfiler(_msgs(["a" * 40, "b" * 80]))
        costs = profiler.cost_per_turn()
        self.assertEqual(len(costs), 2)
        self.assertEqual(costs[0]["tokens"], 10)
        self.assertEqual(costs[0]["cumulative"], 10)
        self.assertEqual(costs[1]["tokens"], 20)
        self.assertEqual(costs[1]["cumulative"], 30)

    def test_empty_messages(self):
        profiler = ConversationProfiler([])
        self.assertEqual(profiler.cost_per_turn(), [])

    def test_turn_index(self):
        profiler = ConversationProfiler(_msgs(["x" * 4]))
        costs = profiler.cost_per_turn()
        self.assertEqual(costs[0]["turn"], 0)

    def test_role_preserved(self):
        msgs = [{"role": "assistant", "content": "hi"}]
        profiler = ConversationProfiler(msgs)
        costs = profiler.cost_per_turn()
        self.assertEqual(costs[0]["role"], "assistant")


class TestHotspots(unittest.TestCase):
    def test_finds_hotspot(self):
        profiler = ConversationProfiler(_msgs(["x" * 5000]))
        hot = profiler.hotspots(threshold=1000)
        self.assertEqual(len(hot), 1)
        self.assertEqual(hot[0]["turn"], 0)

    def test_no_hotspots(self):
        profiler = ConversationProfiler(_msgs(["short"]))
        hot = profiler.hotspots(threshold=1000)
        self.assertEqual(len(hot), 0)

    def test_custom_threshold(self):
        profiler = ConversationProfiler(_msgs(["a" * 20]))
        hot = profiler.hotspots(threshold=4)
        self.assertEqual(len(hot), 1)

    def test_exactly_at_threshold(self):
        # 4000 chars / 4 = 1000 tokens — should match >= threshold
        profiler = ConversationProfiler(_msgs(["a" * 4000]))
        hot = profiler.hotspots(threshold=1000)
        self.assertEqual(len(hot), 1)


class TestWasteDetection(unittest.TestCase):
    def test_empty_turn(self):
        profiler = ConversationProfiler(_msgs(["hello", ""]))
        waste = profiler.waste_detection()
        self.assertEqual(len(waste), 1)
        self.assertEqual(waste[0]["reason"], "empty")

    def test_near_empty_turn(self):
        profiler = ConversationProfiler(_msgs(["ok", "hi"]))
        waste = profiler.waste_detection()
        reasons = [w["reason"] for w in waste]
        self.assertIn("near-empty", reasons)

    def test_duplicate_content(self):
        profiler = ConversationProfiler(_msgs(["Hello World", "Hello World"]))
        waste = profiler.waste_detection()
        dup = [w for w in waste if "duplicate" in w["reason"]]
        self.assertEqual(len(dup), 1)

    def test_no_waste(self):
        profiler = ConversationProfiler(_msgs(["This is a real message", "Another real message"]))
        waste = profiler.waste_detection()
        self.assertEqual(len(waste), 0)

    def test_none_content(self):
        profiler = ConversationProfiler([{"role": "user", "content": None}])
        waste = profiler.waste_detection()
        self.assertEqual(len(waste), 1)


class TestTotalTokens(unittest.TestCase):
    def test_total(self):
        profiler = ConversationProfiler(_msgs(["a" * 100, "b" * 200]))
        self.assertEqual(profiler.total_tokens(), 75)

    def test_empty(self):
        profiler = ConversationProfiler([])
        self.assertEqual(profiler.total_tokens(), 0)


class TestSummary(unittest.TestCase):
    def test_summary_format(self):
        profiler = ConversationProfiler(_msgs(["a" * 100]))
        summary = profiler.summary()
        self.assertIn("Turns: 1", summary)
        self.assertIn("Total tokens:", summary)
        self.assertIn("Hotspots:", summary)
        self.assertIn("Waste turns:", summary)

    def test_summary_empty(self):
        profiler = ConversationProfiler([])
        summary = profiler.summary()
        self.assertIn("Turns: 0", summary)


if __name__ == "__main__":
    unittest.main()
