"""Tests for economics.cost_hook — ModelPricing, CostRecord, CostHook."""
from __future__ import annotations

import unittest

from lidco.economics.cost_hook import CostHook, CostRecord, ModelPricing


class TestModelPricing(unittest.TestCase):
    def test_frozen(self):
        p = ModelPricing(model="gpt-4", input_cost_per_1k=0.03, output_cost_per_1k=0.06)
        with self.assertRaises(AttributeError):
            p.model = "other"  # type: ignore[misc]

    def test_fields(self):
        p = ModelPricing("gpt-3.5-turbo", 0.0015, 0.002)
        self.assertEqual(p.model, "gpt-3.5-turbo")
        self.assertAlmostEqual(p.input_cost_per_1k, 0.0015)
        self.assertAlmostEqual(p.output_cost_per_1k, 0.002)

    def test_equality(self):
        a = ModelPricing("m1", 0.01, 0.02)
        b = ModelPricing("m1", 0.01, 0.02)
        self.assertEqual(a, b)


class TestCostRecord(unittest.TestCase):
    def test_frozen(self):
        r = CostRecord(model="m", input_tokens=10, output_tokens=5, cost=0.01, timestamp="t")
        with self.assertRaises(AttributeError):
            r.cost = 999  # type: ignore[misc]

    def test_fields(self):
        r = CostRecord("gpt-4", 1000, 500, 0.06, "2026-01-01T00:00:00")
        self.assertEqual(r.model, "gpt-4")
        self.assertEqual(r.input_tokens, 1000)
        self.assertEqual(r.output_tokens, 500)
        self.assertAlmostEqual(r.cost, 0.06)
        self.assertEqual(r.timestamp, "2026-01-01T00:00:00")


class TestCostHook(unittest.TestCase):
    def _make_hook(self):
        pricing = (
            ModelPricing("gpt-4", 0.03, 0.06),
            ModelPricing("gpt-3.5-turbo", 0.0015, 0.002),
        )
        return CostHook(pricing=pricing)

    def test_record_returns_cost_record(self):
        hook = self._make_hook()
        rec = hook.record("gpt-4", 1000, 500)
        self.assertIsInstance(rec, CostRecord)
        self.assertEqual(rec.model, "gpt-4")
        # 1000/1000 * 0.03 + 500/1000 * 0.06 = 0.03 + 0.03 = 0.06
        self.assertAlmostEqual(rec.cost, 0.06)

    def test_total_cost(self):
        hook = self._make_hook()
        hook.record("gpt-4", 1000, 1000)
        hook.record("gpt-3.5-turbo", 1000, 1000)
        # gpt-4: 0.03 + 0.06 = 0.09; gpt-3.5: 0.0015 + 0.002 = 0.0035
        self.assertAlmostEqual(hook.total_cost, 0.0935)

    def test_records_returns_tuple(self):
        hook = self._make_hook()
        hook.record("gpt-4", 100, 100)
        self.assertIsInstance(hook.records, tuple)
        self.assertEqual(len(hook.records), 1)

    def test_by_model(self):
        hook = self._make_hook()
        hook.record("gpt-4", 1000, 0)
        hook.record("gpt-4", 1000, 0)
        hook.record("gpt-3.5-turbo", 1000, 0)
        by = hook.by_model()
        self.assertAlmostEqual(by["gpt-4"], 0.06)
        self.assertAlmostEqual(by["gpt-3.5-turbo"], 0.0015)

    def test_unknown_model_zero_cost(self):
        hook = self._make_hook()
        rec = hook.record("unknown-model", 1000, 1000)
        self.assertAlmostEqual(rec.cost, 0.0)

    def test_empty_hook(self):
        hook = CostHook()
        self.assertAlmostEqual(hook.total_cost, 0.0)
        self.assertEqual(hook.records, ())
        self.assertEqual(hook.by_model(), {})

    def test_records_immutable(self):
        hook = self._make_hook()
        hook.record("gpt-4", 100, 100)
        records = hook.records
        self.assertEqual(len(records), 1)
        hook.record("gpt-4", 200, 200)
        # Original tuple should not have changed
        self.assertEqual(len(records), 1)
        self.assertEqual(len(hook.records), 2)

    def test_timestamp_populated(self):
        hook = self._make_hook()
        rec = hook.record("gpt-4", 100, 100)
        self.assertIsInstance(rec.timestamp, str)
        self.assertIn("T", rec.timestamp)

    def test_multiple_models_by_model(self):
        hook = self._make_hook()
        hook.record("gpt-4", 1000, 0)
        hook.record("gpt-3.5-turbo", 1000, 0)
        by = hook.by_model()
        self.assertEqual(len(by), 2)
        self.assertIn("gpt-4", by)
        self.assertIn("gpt-3.5-turbo", by)

    def test_cost_record_equality(self):
        a = CostRecord("m", 10, 5, 0.01, "t")
        b = CostRecord("m", 10, 5, 0.01, "t")
        self.assertEqual(a, b)

    def test_model_pricing_different_not_equal(self):
        a = ModelPricing("m1", 0.01, 0.02)
        b = ModelPricing("m2", 0.01, 0.02)
        self.assertNotEqual(a, b)

    def test_record_accumulates(self):
        hook = self._make_hook()
        hook.record("gpt-4", 100, 100)
        hook.record("gpt-4", 100, 100)
        hook.record("gpt-4", 100, 100)
        self.assertEqual(len(hook.records), 3)

    def test_total_cost_after_empty_is_zero(self):
        hook = CostHook(pricing=())
        hook.record("anything", 1000, 1000)
        self.assertAlmostEqual(hook.total_cost, 0.0)

    def test_zero_tokens(self):
        hook = self._make_hook()
        rec = hook.record("gpt-4", 0, 0)
        self.assertAlmostEqual(rec.cost, 0.0)


class TestCostHookAllExport(unittest.TestCase):
    def test_all(self):
        from lidco.economics import cost_hook

        self.assertIn("ModelPricing", cost_hook.__all__)
        self.assertIn("CostRecord", cost_hook.__all__)
        self.assertIn("CostHook", cost_hook.__all__)


if __name__ == "__main__":
    unittest.main()
