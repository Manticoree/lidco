"""Tests for Q139 ProgressBar."""
from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from lidco.ui.progress_bar import ProgressBar, ProgressState


class TestProgressState(unittest.TestCase):
    def test_dataclass_fields(self):
        ps = ProgressState(current=5, total=10, label="x", started_at=1.0, updated_at=2.0)
        self.assertEqual(ps.current, 5)
        self.assertEqual(ps.total, 10)
        self.assertEqual(ps.label, "x")
        self.assertEqual(ps.started_at, 1.0)
        self.assertEqual(ps.updated_at, 2.0)


class TestProgressBarInit(unittest.TestCase):
    def test_defaults(self):
        bar = ProgressBar(total=100)
        self.assertEqual(bar._total, 100)
        self.assertEqual(bar._label, "")
        self.assertEqual(bar._width, 40)
        self.assertFalse(bar.is_complete)

    def test_custom_params(self):
        bar = ProgressBar(total=50, label="Test", width=20, fill_char="#", empty_char=".")
        self.assertEqual(bar._total, 50)
        self.assertEqual(bar._label, "Test")
        self.assertEqual(bar._width, 20)
        self.assertEqual(bar._fill_char, "#")
        self.assertEqual(bar._empty_char, ".")

    def test_negative_total_raises(self):
        with self.assertRaises(ValueError):
            ProgressBar(total=-1)

    def test_zero_total(self):
        bar = ProgressBar(total=0)
        self.assertTrue(bar.is_complete)
        self.assertEqual(bar.percentage, 100.0)

    def test_width_min_clamp(self):
        bar = ProgressBar(total=10, width=0)
        self.assertEqual(bar._width, 1)


class TestProgressBarUpdate(unittest.TestCase):
    def test_update_sets_current(self):
        bar = ProgressBar(total=100)
        bar.update(50)
        self.assertEqual(bar._current, 50)

    def test_update_clamps_upper(self):
        bar = ProgressBar(total=10)
        bar.update(20)
        self.assertEqual(bar._current, 10)

    def test_update_clamps_lower(self):
        bar = ProgressBar(total=10)
        bar.update(-5)
        self.assertEqual(bar._current, 0)

    def test_advance_increments(self):
        bar = ProgressBar(total=10)
        bar.advance()
        self.assertEqual(bar._current, 1)
        bar.advance(3)
        self.assertEqual(bar._current, 4)

    def test_advance_default_one(self):
        bar = ProgressBar(total=10)
        bar.advance()
        bar.advance()
        self.assertEqual(bar._current, 2)


class TestProgressBarPercentage(unittest.TestCase):
    def test_zero_percent(self):
        bar = ProgressBar(total=100)
        self.assertAlmostEqual(bar.percentage, 0.0)

    def test_fifty_percent(self):
        bar = ProgressBar(total=100)
        bar.update(50)
        self.assertAlmostEqual(bar.percentage, 50.0)

    def test_hundred_percent(self):
        bar = ProgressBar(total=100)
        bar.update(100)
        self.assertAlmostEqual(bar.percentage, 100.0)


class TestProgressBarETA(unittest.TestCase):
    def test_eta_none_at_start(self):
        bar = ProgressBar(total=100)
        self.assertIsNone(bar.eta)

    def test_eta_returns_value_when_progressed(self):
        bar = ProgressBar(total=100)
        bar._started_at = time.monotonic() - 10.0
        bar._current = 50
        bar._updated_at = time.monotonic()
        eta = bar.eta
        self.assertIsNotNone(eta)
        self.assertGreater(eta, 0)

    def test_eta_zero_total(self):
        bar = ProgressBar(total=0)
        self.assertIsNone(bar.eta)


class TestProgressBarRender(unittest.TestCase):
    def test_render_contains_label(self):
        bar = ProgressBar(total=10, label="Build")
        result = bar.render()
        self.assertIn("Build", result)

    def test_render_contains_percentage(self):
        bar = ProgressBar(total=10)
        bar.update(5)
        result = bar.render()
        self.assertIn("50%", result)

    def test_render_contains_counts(self):
        bar = ProgressBar(total=20)
        bar.update(13)
        result = bar.render()
        self.assertIn("(13/20)", result)

    def test_render_contains_bar_chars(self):
        bar = ProgressBar(total=10, width=10, fill_char="#", empty_char=".")
        bar.update(5)
        result = bar.render()
        self.assertIn("#####.....", result)

    def test_render_no_label(self):
        bar = ProgressBar(total=10)
        result = bar.render()
        self.assertTrue(result.startswith("["))


class TestProgressBarFinish(unittest.TestCase):
    def test_finish_sets_complete(self):
        bar = ProgressBar(total=100)
        bar.finish()
        self.assertTrue(bar.is_complete)
        self.assertAlmostEqual(bar.percentage, 100.0)

    def test_finish_sets_finished_flag(self):
        bar = ProgressBar(total=100)
        bar.finish()
        self.assertTrue(bar._finished)


class TestProgressBarState(unittest.TestCase):
    def test_state_snapshot(self):
        bar = ProgressBar(total=10, label="X")
        bar.update(3)
        state = bar.state
        self.assertIsInstance(state, ProgressState)
        self.assertEqual(state.current, 3)
        self.assertEqual(state.total, 10)
        self.assertEqual(state.label, "X")


if __name__ == "__main__":
    unittest.main()
