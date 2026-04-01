"""Tests for economics.budget_hook — BudgetConfig, BudgetStatus, BudgetExceeded, BudgetHook."""
from __future__ import annotations

import unittest

from lidco.economics.budget_hook import (
    BudgetConfig,
    BudgetExceeded,
    BudgetHook,
    BudgetStatus,
)


class TestBudgetConfig(unittest.TestCase):
    def test_frozen(self):
        c = BudgetConfig(soft_limit=1.0, hard_limit=2.0, period="session")
        with self.assertRaises(AttributeError):
            c.soft_limit = 5.0  # type: ignore[misc]

    def test_fields(self):
        c = BudgetConfig(0.5, 1.0, "daily")
        self.assertAlmostEqual(c.soft_limit, 0.5)
        self.assertAlmostEqual(c.hard_limit, 1.0)
        self.assertEqual(c.period, "daily")

    def test_equality(self):
        a = BudgetConfig(1.0, 2.0, "session")
        b = BudgetConfig(1.0, 2.0, "session")
        self.assertEqual(a, b)


class TestBudgetStatus(unittest.TestCase):
    def test_frozen(self):
        s = BudgetStatus(allowed=True, warning=False, remaining=1.0)
        with self.assertRaises(AttributeError):
            s.allowed = False  # type: ignore[misc]

    def test_fields(self):
        s = BudgetStatus(True, True, 0.5)
        self.assertTrue(s.allowed)
        self.assertTrue(s.warning)
        self.assertAlmostEqual(s.remaining, 0.5)


class TestBudgetExceeded(unittest.TestCase):
    def test_is_exception(self):
        self.assertTrue(issubclass(BudgetExceeded, Exception))

    def test_can_raise(self):
        with self.assertRaises(BudgetExceeded):
            raise BudgetExceeded("over budget")


class TestBudgetHook(unittest.TestCase):
    def _make_hook(self, soft=0.5, hard=1.0, period="session"):
        config = BudgetConfig(soft_limit=soft, hard_limit=hard, period=period)
        return BudgetHook(config)

    def test_check_under_soft(self):
        hook = self._make_hook(soft=0.5, hard=1.0)
        status = hook.check(0.2)
        self.assertTrue(status.allowed)
        self.assertFalse(status.warning)
        self.assertAlmostEqual(status.remaining, 0.8)

    def test_check_in_warning_zone(self):
        hook = self._make_hook(soft=0.5, hard=1.0)
        status = hook.check(0.7)
        self.assertTrue(status.allowed)
        self.assertTrue(status.warning)
        self.assertAlmostEqual(status.remaining, 0.3)

    def test_check_at_soft_limit(self):
        hook = self._make_hook(soft=0.5, hard=1.0)
        status = hook.check(0.5)
        self.assertTrue(status.allowed)
        self.assertTrue(status.warning)

    def test_check_at_hard_limit(self):
        hook = self._make_hook(soft=0.5, hard=1.0)
        status = hook.check(1.0)
        self.assertFalse(status.allowed)
        self.assertFalse(status.warning)
        self.assertAlmostEqual(status.remaining, 0.0)

    def test_check_over_hard_limit(self):
        hook = self._make_hook(soft=0.5, hard=1.0)
        status = hook.check(1.5)
        self.assertFalse(status.allowed)
        self.assertAlmostEqual(status.remaining, 0.0)

    def test_is_exceeded_true(self):
        hook = self._make_hook(hard=1.0)
        self.assertTrue(hook.is_exceeded(1.0))
        self.assertTrue(hook.is_exceeded(2.0))

    def test_is_exceeded_false(self):
        hook = self._make_hook(hard=1.0)
        self.assertFalse(hook.is_exceeded(0.99))

    def test_zero_cost(self):
        hook = self._make_hook(soft=0.5, hard=1.0)
        status = hook.check(0.0)
        self.assertTrue(status.allowed)
        self.assertFalse(status.warning)
        self.assertAlmostEqual(status.remaining, 1.0)

    def test_monthly_period(self):
        hook = self._make_hook(period="monthly")
        status = hook.check(0.0)
        self.assertTrue(status.allowed)

    def test_remaining_never_negative(self):
        hook = self._make_hook(hard=1.0)
        status = hook.check(5.0)
        self.assertGreaterEqual(status.remaining, 0.0)

    def test_warning_not_set_when_exceeded(self):
        hook = self._make_hook(soft=0.5, hard=1.0)
        status = hook.check(1.0)
        self.assertFalse(status.warning)

    def test_is_exceeded_exactly_at_limit(self):
        hook = self._make_hook(hard=0.01)
        self.assertTrue(hook.is_exceeded(0.01))

    def test_check_returns_budget_status(self):
        hook = self._make_hook()
        result = hook.check(0.0)
        self.assertIsInstance(result, BudgetStatus)

    def test_daily_period_accepted(self):
        hook = self._make_hook(period="daily")
        self.assertIsNotNone(hook.check(0.0))

    def test_budget_config_equality_different(self):
        a = BudgetConfig(1.0, 2.0, "session")
        b = BudgetConfig(1.0, 2.0, "daily")
        self.assertNotEqual(a, b)

    def test_budget_status_equality(self):
        a = BudgetStatus(True, False, 1.0)
        b = BudgetStatus(True, False, 1.0)
        self.assertEqual(a, b)


class TestBudgetHookAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.economics import budget_hook

        self.assertIn("BudgetConfig", budget_hook.__all__)
        self.assertIn("BudgetStatus", budget_hook.__all__)
        self.assertIn("BudgetExceeded", budget_hook.__all__)
        self.assertIn("BudgetHook", budget_hook.__all__)


if __name__ == "__main__":
    unittest.main()
