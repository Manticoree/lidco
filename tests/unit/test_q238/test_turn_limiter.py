"""Tests for TurnLimiter (Q238)."""
from __future__ import annotations

import unittest

from lidco.safety.turn_limiter import (
    LimitAction,
    TurnLimitResult,
    TurnLimiter,
)


class TestLimitAction(unittest.TestCase):
    def test_values(self):
        self.assertEqual(LimitAction.CONTINUE.value, "continue")
        self.assertEqual(LimitAction.STOP.value, "stop")
        self.assertEqual(LimitAction.OVERRIDE.value, "override")

    def test_all_actions(self):
        self.assertEqual(len(LimitAction), 4)


class TestTurnLimitResult(unittest.TestCase):
    def test_frozen(self):
        r = TurnLimitResult(current_turn=1, max_turns=100, action=LimitAction.CONTINUE)
        with self.assertRaises(AttributeError):
            r.current_turn = 2  # type: ignore[misc]

    def test_defaults(self):
        r = TurnLimitResult(current_turn=0, max_turns=100, action=LimitAction.CONTINUE)
        self.assertEqual(r.message, "")


class TestTurnLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = TurnLimiter(max_turns=100, warn_at=0.8)

    def test_continue_below_threshold(self):
        result = self.limiter.check(50)
        self.assertEqual(result.action, LimitAction.CONTINUE)

    def test_warn_at_threshold(self):
        result = self.limiter.check(80)
        self.assertEqual(result.action, LimitAction.WARN)
        self.assertIn("remaining", result.message)

    def test_stop_at_limit(self):
        result = self.limiter.check(100)
        self.assertEqual(result.action, LimitAction.STOP)

    def test_stop_above_limit(self):
        result = self.limiter.check(150)
        self.assertEqual(result.action, LimitAction.STOP)

    def test_override_extends_limit(self):
        self.limiter.override(20)
        result = self.limiter.check(100)
        # After override, max is 120, so 100 is in warn zone
        self.assertNotEqual(result.action, LimitAction.STOP)

    def test_remaining(self):
        self.assertEqual(self.limiter.remaining(70), 30)
        self.assertEqual(self.limiter.remaining(100), 0)
        self.assertEqual(self.limiter.remaining(110), 0)

    def test_percentage(self):
        self.assertAlmostEqual(self.limiter.percentage(50), 0.5)
        self.assertAlmostEqual(self.limiter.percentage(100), 1.0)

    def test_set_limit(self):
        self.limiter.set_limit(200)
        self.assertEqual(self.limiter.remaining(100), 100)

    def test_summary(self):
        s = self.limiter.summary(50)
        self.assertIn("50/100", s)
        self.assertIn("50%", s)
        self.assertIn("50 remaining", s)


if __name__ == "__main__":
    unittest.main()
