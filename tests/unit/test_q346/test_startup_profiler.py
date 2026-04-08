"""Tests for lidco.stability.startup_profiler."""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from lidco.stability.startup_profiler import StartupProfiler


class TestProfileImports(unittest.TestCase):
    def setUp(self):
        self.profiler = StartupProfiler()

    def test_returns_list_of_dicts(self):
        result = self.profiler.profile_imports(["os", "sys"])
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_dict_has_required_keys(self):
        result = self.profiler.profile_imports(["json"])
        entry = result[0]
        self.assertIn("module", entry)
        self.assertIn("time_ms", entry)
        self.assertIn("success", entry)
        self.assertIn("error", entry)

    def test_successful_import_success_true(self):
        result = self.profiler.profile_imports(["os"])
        self.assertTrue(result[0]["success"])
        self.assertIsNone(result[0]["error"])

    def test_failed_import_success_false(self):
        result = self.profiler.profile_imports(["_nonexistent_module_xyz_123"])
        self.assertFalse(result[0]["success"])
        self.assertIsNotNone(result[0]["error"])

    def test_time_ms_is_float(self):
        result = self.profiler.profile_imports(["re"])
        self.assertIsInstance(result[0]["time_ms"], float)

    def test_time_ms_non_negative(self):
        result = self.profiler.profile_imports(["json"])
        self.assertGreaterEqual(result[0]["time_ms"], 0.0)

    def test_module_name_in_result(self):
        result = self.profiler.profile_imports(["pathlib"])
        self.assertEqual(result[0]["module"], "pathlib")

    def test_timings_stored_internally(self):
        self.profiler.profile_imports(["collections"])
        self.assertIn("collections", self.profiler._timings)

    def test_multiple_modules_ordered(self):
        modules = ["os", "sys", "re"]
        result = self.profiler.profile_imports(modules)
        names = [r["module"] for r in result]
        self.assertEqual(names, modules)

    def test_empty_module_list(self):
        result = self.profiler.profile_imports([])
        self.assertEqual(result, [])


class TestFindLazyOpportunities(unittest.TestCase):
    def setUp(self):
        self.profiler = StartupProfiler()

    def test_detects_heavy_import(self):
        src = "import numpy\n\ndef foo():\n    pass\n"
        opps = self.profiler.find_lazy_opportunities(src)
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps[0]["module"], "numpy")

    def test_no_heavy_imports(self):
        src = "import os\nimport sys\n"
        opps = self.profiler.find_lazy_opportunities(src)
        self.assertEqual(opps, [])

    def test_result_dict_keys(self):
        src = "import pandas\n"
        opps = self.profiler.find_lazy_opportunities(src)
        entry = opps[0]
        self.assertIn("line", entry)
        self.assertIn("module", entry)
        self.assertIn("suggestion", entry)
        self.assertIn("estimated_savings_ms", entry)

    def test_line_number_correct(self):
        src = "\nimport torch\n"
        opps = self.profiler.find_lazy_opportunities(src)
        self.assertEqual(opps[0]["line"], 2)

    def test_estimated_savings_positive(self):
        src = "import tensorflow\n"
        opps = self.profiler.find_lazy_opportunities(src)
        self.assertGreater(opps[0]["estimated_savings_ms"], 0.0)

    def test_from_import_detected(self):
        src = "from pandas import DataFrame\n"
        opps = self.profiler.find_lazy_opportunities(src)
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps[0]["module"], "pandas")


class TestAnalyzeColdStart(unittest.TestCase):
    def setUp(self):
        self.profiler = StartupProfiler()

    def test_total_ms_sum(self):
        timings = {"a": 100.0, "b": 200.0, "c": 50.0}
        result = self.profiler.analyze_cold_start(timings)
        self.assertAlmostEqual(result["total_ms"], 350.0)

    def test_top_5_limited(self):
        timings = {f"mod_{i}": float(i * 10) for i in range(10)}
        result = self.profiler.analyze_cold_start(timings)
        self.assertLessEqual(len(result["top_5"]), 5)

    def test_top_5_sorted_descending(self):
        timings = {"fast": 10.0, "slow": 500.0, "medium": 100.0}
        result = self.profiler.analyze_cold_start(timings)
        times = [ms for _, ms in result["top_5"]]
        self.assertEqual(times, sorted(times, reverse=True))

    def test_suggestions_for_very_slow_module(self):
        timings = {"heavy_lib": 600.0}
        result = self.profiler.analyze_cold_start(timings)
        self.assertTrue(len(result["suggestions"]) > 0)

    def test_no_suggestions_for_fast_imports(self):
        timings = {"fast": 1.0, "also_fast": 2.0}
        result = self.profiler.analyze_cold_start(timings)
        self.assertEqual(result["suggestions"], [])

    def test_empty_timings(self):
        result = self.profiler.analyze_cold_start({})
        self.assertEqual(result["total_ms"], 0.0)
        self.assertEqual(result["top_5"], [])


class TestGenerateReport(unittest.TestCase):
    def setUp(self):
        self.profiler = StartupProfiler()

    def test_no_timings_message(self):
        report = self.profiler.generate_report()
        self.assertIn("No startup timings", report)

    def test_report_contains_total(self):
        self.profiler._timings = {"json": 5.0, "os": 2.0}
        report = self.profiler.generate_report()
        self.assertIn("Total startup time", report)

    def test_report_contains_module_names(self):
        self.profiler._timings = {"mymodule": 50.0}
        report = self.profiler.generate_report()
        self.assertIn("mymodule", report)


if __name__ == "__main__":
    unittest.main()
