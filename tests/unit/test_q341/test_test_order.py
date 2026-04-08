"""Tests for TestOrderAnalyzer (Q341 Task 3)."""
from __future__ import annotations

import unittest


class TestDetectOrderDependence(unittest.TestCase):
    def setUp(self):
        from lidco.stability.test_order import TestOrderAnalyzer
        self.a = TestOrderAnalyzer()

    def test_empty_results_returns_empty(self):
        self.assertEqual(self.a.detect_order_dependence([]), [])

    def test_consistent_pass_not_flagged(self):
        results = [
            {"name": "test_a", "order_index": 0, "passed": True},
            {"name": "test_a", "order_index": 1, "passed": True},
        ]
        self.assertEqual(self.a.detect_order_dependence(results), [])

    def test_consistent_fail_not_flagged(self):
        results = [
            {"name": "test_b", "order_index": 0, "passed": False},
            {"name": "test_b", "order_index": 1, "passed": False},
        ]
        self.assertEqual(self.a.detect_order_dependence(results), [])

    def test_mixed_results_flagged(self):
        results = [
            {"name": "test_flaky", "order_index": 0, "passed": True},
            {"name": "test_flaky", "order_index": 1, "passed": False},
        ]
        findings = self.a.detect_order_dependence(results)
        self.assertTrue(any(f["test_name"] == "test_flaky" for f in findings))

    def test_evidence_contains_indices(self):
        results = [
            {"name": "test_x", "order_index": 2, "passed": True},
            {"name": "test_x", "order_index": 5, "passed": False},
        ]
        findings = self.a.detect_order_dependence(results)
        item = next(f for f in findings if f["test_name"] == "test_x")
        self.assertIn("2", item["evidence"])
        self.assertIn("5", item["evidence"])


class TestValidateShuffle(unittest.TestCase):
    def setUp(self):
        from lidco.stability.test_order import TestOrderAnalyzer
        self.a = TestOrderAnalyzer()

    def test_identical_results_stable(self):
        names = ["a", "b", "c"]
        result = self.a.validate_shuffle(names, [True, True, True], [True, True, True])
        self.assertFalse(result["order_dependent"])
        self.assertEqual(result["failures"], [])

    def test_different_results_detected(self):
        names = ["a", "b"]
        result = self.a.validate_shuffle(names, [True, True], [True, False])
        self.assertTrue(result["order_dependent"])
        self.assertIn("b", result["failures"])

    def test_total_count_correct(self):
        names = ["a", "b", "c"]
        result = self.a.validate_shuffle(names, [True, False, True], [True, True, True])
        self.assertEqual(result["total"], 3)

    def test_stable_count_correct(self):
        names = ["a", "b", "c"]
        result = self.a.validate_shuffle(names, [True, True, True], [True, False, True])
        self.assertEqual(result["stable_count"], 2)

    def test_empty_inputs(self):
        result = self.a.validate_shuffle([], [], [])
        self.assertFalse(result["order_dependent"])
        self.assertEqual(result["total"], 0)


class TestAnalyzeDependencies(unittest.TestCase):
    def setUp(self):
        from lidco.stability.test_order import TestOrderAnalyzer
        self.a = TestOrderAnalyzer()

    def test_empty_source_returns_empty(self):
        self.assertEqual(self.a.analyze_dependencies(""), [])

    def test_direct_test_call_detected(self):
        source = (
            "def test_a(): pass\n"
            "def test_b():\n"
            "    test_a()\n"
        )
        result = self.a.analyze_dependencies(source)
        self.assertTrue(
            any(r["test_name"] == "test_b" and r["depends_on"] == "test_a" for r in result)
        )

    def test_independent_tests_no_dependency(self):
        source = (
            "def test_a():\n"
            "    assert 1 == 1\n"
            "def test_b():\n"
            "    assert 2 == 2\n"
        )
        result = self.a.analyze_dependencies(source)
        self.assertEqual(result, [])

    def test_global_keyword_dependency_detected(self):
        source = (
            "counter = 0\n"
            "def test_mutate():\n"
            "    global counter\n"
            "    counter += 1\n"
        )
        result = self.a.analyze_dependencies(source)
        self.assertTrue(
            any("counter" in r["depends_on"] for r in result)
        )


class TestSuggestFixes(unittest.TestCase):
    def setUp(self):
        from lidco.stability.test_order import TestOrderAnalyzer
        self.a = TestOrderAnalyzer()

    def test_empty_findings_returns_no_issues_message(self):
        result = self.a.suggest_fixes([])
        self.assertEqual(result, ["No order-dependence issues detected."])

    def test_direct_call_suggestion_mentions_tests(self):
        findings = [
            {"test_name": "test_b", "depends_on": "test_a", "type": "direct_call"}
        ]
        result = self.a.suggest_fixes(findings)
        self.assertTrue(any("test_b" in s for s in result))
        self.assertTrue(any("test_a" in s for s in result))

    def test_shared_global_suggestion_mentions_variable(self):
        findings = [
            {
                "test_name": "test_x",
                "depends_on": "global:my_var",
                "type": "shared_global",
            }
        ]
        result = self.a.suggest_fixes(findings)
        self.assertTrue(any("my_var" in s for s in result))

    def test_order_dependence_finding_suggestion(self):
        findings = [
            {
                "test_name": "test_flaky",
                "issue": "Test result varies with execution order",
            }
        ]
        result = self.a.suggest_fixes(findings)
        self.assertTrue(any("test_flaky" in s for s in result))


if __name__ == "__main__":
    unittest.main()
