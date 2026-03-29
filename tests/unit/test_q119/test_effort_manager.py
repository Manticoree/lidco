"""Tests for EffortManager — Task 729."""

from __future__ import annotations

import json
import unittest

from lidco.config.effort_manager import (
    EffortBudget,
    EffortLevel,
    EffortManager,
    EFFORT_BUDGETS,
)


class TestEffortLevel(unittest.TestCase):
    """EffortLevel enum basics."""

    def test_values(self):
        self.assertEqual(EffortLevel.LOW.value, "low")
        self.assertEqual(EffortLevel.MEDIUM.value, "medium")
        self.assertEqual(EffortLevel.HIGH.value, "high")
        self.assertEqual(EffortLevel.AUTO.value, "auto")

    def test_from_string(self):
        self.assertEqual(EffortLevel("low"), EffortLevel.LOW)
        self.assertEqual(EffortLevel("high"), EffortLevel.HIGH)

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            EffortLevel("ultra")


class TestEffortBudget(unittest.TestCase):
    """EffortBudget dataclass."""

    def test_create_budget(self):
        b = EffortBudget(max_tokens=1000, thinking_tokens=200, temperature=0.5)
        self.assertEqual(b.max_tokens, 1000)
        self.assertEqual(b.thinking_tokens, 200)
        self.assertEqual(b.temperature, 0.5)

    def test_predefined_budgets_exist(self):
        self.assertIn(EffortLevel.LOW, EFFORT_BUDGETS)
        self.assertIn(EffortLevel.MEDIUM, EFFORT_BUDGETS)
        self.assertIn(EffortLevel.HIGH, EFFORT_BUDGETS)

    def test_low_budget_values(self):
        b = EFFORT_BUDGETS[EffortLevel.LOW]
        self.assertEqual(b.max_tokens, 2048)
        self.assertEqual(b.thinking_tokens, 512)
        self.assertEqual(b.temperature, 0.3)

    def test_medium_budget_values(self):
        b = EFFORT_BUDGETS[EffortLevel.MEDIUM]
        self.assertEqual(b.max_tokens, 8192)
        self.assertEqual(b.thinking_tokens, 2048)
        self.assertEqual(b.temperature, 0.7)

    def test_high_budget_values(self):
        b = EFFORT_BUDGETS[EffortLevel.HIGH]
        self.assertEqual(b.max_tokens, 32000)
        self.assertEqual(b.thinking_tokens, 8000)
        self.assertEqual(b.temperature, 1.0)


class TestEffortManager(unittest.TestCase):
    """EffortManager core functionality."""

    def _manager(self, stored=None):
        written = {}

        def write_fn(path, data):
            written[path] = data

        def read_fn(path):
            if stored:
                return stored
            raise FileNotFoundError

        mgr = EffortManager(store_path="/tmp/effort.json", write_fn=write_fn, read_fn=read_fn)
        mgr._written = written  # attach for assertions
        return mgr

    def test_default_level_is_medium(self):
        mgr = self._manager()
        self.assertEqual(mgr.level, EffortLevel.MEDIUM)

    def test_set_level_by_string(self):
        mgr = self._manager()
        budget = mgr.set_level("low")
        self.assertEqual(mgr.level, EffortLevel.LOW)
        self.assertIsInstance(budget, EffortBudget)

    def test_set_level_by_enum(self):
        mgr = self._manager()
        budget = mgr.set_level(EffortLevel.HIGH)
        self.assertEqual(mgr.level, EffortLevel.HIGH)
        self.assertEqual(budget.max_tokens, 32000)

    def test_set_level_persists(self):
        mgr = self._manager()
        mgr.set_level("low")
        self.assertIn("/tmp/effort.json", mgr._written)

    def test_set_level_returns_correct_budget(self):
        mgr = self._manager()
        budget = mgr.set_level("high")
        self.assertEqual(budget, EFFORT_BUDGETS[EffortLevel.HIGH])

    def test_set_level_invalid_raises(self):
        mgr = self._manager()
        with self.assertRaises(ValueError):
            mgr.set_level("ultra")

    def test_get_budget_current(self):
        mgr = self._manager()
        budget = mgr.get_budget()
        self.assertEqual(budget, EFFORT_BUDGETS[EffortLevel.MEDIUM])

    def test_get_budget_specific_level(self):
        mgr = self._manager()
        budget = mgr.get_budget(EffortLevel.LOW)
        self.assertEqual(budget, EFFORT_BUDGETS[EffortLevel.LOW])

    def test_get_budget_after_set(self):
        mgr = self._manager()
        mgr.set_level("high")
        budget = mgr.get_budget()
        self.assertEqual(budget, EFFORT_BUDGETS[EffortLevel.HIGH])

    def test_auto_select_short_prompt(self):
        mgr = self._manager()
        level = mgr.auto_select(3)
        self.assertEqual(level, EffortLevel.LOW)

    def test_auto_select_five_words(self):
        mgr = self._manager()
        level = mgr.auto_select(5)
        self.assertEqual(level, EffortLevel.LOW)

    def test_auto_select_medium_prompt(self):
        mgr = self._manager()
        level = mgr.auto_select(25)
        self.assertEqual(level, EffortLevel.MEDIUM)

    def test_auto_select_six_words(self):
        mgr = self._manager()
        level = mgr.auto_select(6)
        self.assertEqual(level, EffortLevel.MEDIUM)

    def test_auto_select_fifty_words(self):
        mgr = self._manager()
        level = mgr.auto_select(50)
        self.assertEqual(level, EffortLevel.MEDIUM)

    def test_auto_select_long_prompt(self):
        mgr = self._manager()
        level = mgr.auto_select(100)
        self.assertEqual(level, EffortLevel.HIGH)

    def test_auto_select_fifty_one_words(self):
        mgr = self._manager()
        level = mgr.auto_select(51)
        self.assertEqual(level, EffortLevel.HIGH)

    def test_auto_select_zero_words(self):
        mgr = self._manager()
        level = mgr.auto_select(0)
        self.assertEqual(level, EffortLevel.LOW)

    def test_load_from_store(self):
        stored = json.dumps({"level": "high"})
        mgr = self._manager(stored=stored)
        mgr.load()
        self.assertEqual(mgr.level, EffortLevel.HIGH)

    def test_load_missing_file(self):
        mgr = self._manager()
        mgr.load()  # should not raise
        self.assertEqual(mgr.level, EffortLevel.MEDIUM)

    def test_load_invalid_json(self):
        mgr = self._manager(stored="not json")
        mgr.load()  # should not raise
        self.assertEqual(mgr.level, EffortLevel.MEDIUM)

    def test_load_invalid_level_in_store(self):
        mgr = self._manager(stored=json.dumps({"level": "ultra"}))
        mgr.load()  # should not raise, keep default
        self.assertEqual(mgr.level, EffortLevel.MEDIUM)

    def test_get_budget_auto_defaults_medium(self):
        mgr = self._manager()
        mgr.set_level("auto")
        budget = mgr.get_budget()
        # AUTO defaults to MEDIUM
        self.assertEqual(budget, EFFORT_BUDGETS[EffortLevel.MEDIUM])

    def test_set_level_auto_accepted(self):
        mgr = self._manager()
        mgr.set_level("auto")
        self.assertEqual(mgr.level, EffortLevel.AUTO)

    def test_persist_format_is_json(self):
        mgr = self._manager()
        mgr.set_level("low")
        data = json.loads(mgr._written["/tmp/effort.json"])
        self.assertEqual(data["level"], "low")


class TestEffortManagerEdgeCases(unittest.TestCase):
    """Edge cases."""

    def test_set_level_case_insensitive(self):
        mgr = EffortManager(
            store_path="/tmp/e.json",
            write_fn=lambda p, d: None,
            read_fn=lambda p: (_ for _ in ()).throw(FileNotFoundError),
        )
        # Should accept uppercase
        budget = mgr.set_level("LOW")
        self.assertEqual(mgr.level, EffortLevel.LOW)


if __name__ == "__main__":
    unittest.main()
