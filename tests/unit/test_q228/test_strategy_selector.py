"""Tests for budget.strategy_selector."""
from __future__ import annotations

import unittest

from lidco.budget.strategy_selector import (
    PressureLevel,
    StrategyConfig,
    StrategySelector,
)


class TestPressureLevel(unittest.TestCase):
    def test_values(self):
        self.assertEqual(PressureLevel.LOW, "low")
        self.assertEqual(PressureLevel.CRITICAL, "critical")


class TestStrategyConfig(unittest.TestCase):
    def test_frozen(self):
        cfg = StrategyConfig(name="x", pressure=PressureLevel.LOW)
        with self.assertRaises(AttributeError):
            cfg.name = "y"  # type: ignore[misc]

    def test_defaults(self):
        cfg = StrategyConfig(name="a", pressure=PressureLevel.MEDIUM)
        self.assertEqual(cfg.keep_recent, 10)
        self.assertTrue(cfg.trim_tool_results)


class TestStrategySelector(unittest.TestCase):
    def setUp(self):
        self.sel = StrategySelector()

    def test_classify_low(self):
        self.assertEqual(self.sel.classify_pressure(0.3), PressureLevel.LOW)

    def test_classify_medium(self):
        self.assertEqual(self.sel.classify_pressure(0.55), PressureLevel.MEDIUM)

    def test_classify_high(self):
        self.assertEqual(self.sel.classify_pressure(0.8), PressureLevel.HIGH)

    def test_classify_critical(self):
        self.assertEqual(self.sel.classify_pressure(0.95), PressureLevel.CRITICAL)

    def test_select_returns_config(self):
        cfg = self.sel.select(0.6)
        self.assertEqual(cfg.pressure, PressureLevel.MEDIUM)
        self.assertEqual(cfg.name, "trim_tools")

    def test_register_custom_strategy(self):
        custom = StrategyConfig(name="custom", pressure=PressureLevel.LOW, keep_recent=50)
        self.sel.register_strategy(custom)
        cfg = self.sel.select(0.1)
        self.assertEqual(cfg.name, "custom")
        self.assertEqual(cfg.keep_recent, 50)

    def test_get_all(self):
        all_s = self.sel.get_all()
        self.assertEqual(len(all_s), 4)

    def test_apply_keeps_system(self):
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        cfg = self.sel.select(0.95)  # CRITICAL, keep_recent=5
        result = self.sel.apply_to_messages(msgs, cfg)
        self.assertTrue(any(m["role"] == "system" for m in result))

    def test_apply_trims_tool_results(self):
        big_content = "x" * 5000
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "tool", "content": big_content},
            *[{"role": "user", "content": f"msg{i}"} for i in range(3)],
        ]
        cfg = StrategyConfig(
            name="test", pressure=PressureLevel.HIGH,
            keep_recent=2, trim_tool_results=True, max_tool_result_tokens=100,
        )
        result = self.sel.apply_to_messages(msgs, cfg)
        tool_msgs = [m for m in result if m.get("role") == "tool"]
        self.assertTrue(all("[trimmed]" in m["content"] for m in tool_msgs))

    def test_apply_summarizes_assistant(self):
        msgs = [
            {"role": "system", "content": "sys"},
            {"role": "assistant", "content": "a" * 1000},
            {"role": "user", "content": "u"},
        ]
        cfg = StrategyConfig(
            name="test", pressure=PressureLevel.HIGH,
            keep_recent=1, summarize_older=True,
        )
        result = self.sel.apply_to_messages(msgs, cfg)
        asst = [m for m in result if m.get("role") == "assistant"]
        self.assertTrue(any("[summarized]" in m["content"] for m in asst))

    def test_summary(self):
        s = self.sel.summary()
        self.assertIn("4 strategies", s)
        self.assertIn("noop", s)


if __name__ == "__main__":
    unittest.main()
