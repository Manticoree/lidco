"""Tests for computer_use.visual_test."""
from __future__ import annotations

import unittest

from lidco.computer_use.screenshot import ScreenRegion, ScreenshotResult
from lidco.computer_use.visual_test import VisualAssertion, VisualTestResult, VisualTestRunner


class TestAssertTextPresent(unittest.TestCase):
    def setUp(self):
        self.runner = VisualTestRunner()

    def test_text_found(self):
        shot = ScreenshotResult(width=100, height=100, text_content="Welcome to LIDCO")
        assertion = self.runner.assert_text_present(shot, "Welcome")
        self.assertTrue(assertion.passed)
        self.assertIn("found", assertion.message)

    def test_text_not_found(self):
        shot = ScreenshotResult(width=100, height=100, text_content="Hello")
        assertion = self.runner.assert_text_present(shot, "Goodbye")
        self.assertFalse(assertion.passed)
        self.assertIn("not found", assertion.message)

    def test_text_case_insensitive(self):
        shot = ScreenshotResult(width=100, height=100, text_content="HELLO")
        assertion = self.runner.assert_text_present(shot, "hello")
        self.assertTrue(assertion.passed)


class TestAssertRegionExists(unittest.TestCase):
    def setUp(self):
        self.runner = VisualTestRunner()

    def test_region_found(self):
        region = ScreenRegion(x=0, y=0, width=50, height=20)
        shot = ScreenshotResult(
            width=100, height=100, text_content="Submit", regions=(region,)
        )
        assertion = self.runner.assert_region_exists(shot, "Submit")
        self.assertTrue(assertion.passed)

    def test_region_not_found(self):
        shot = ScreenshotResult(width=100, height=100, text_content="Hello")
        assertion = self.runner.assert_region_exists(shot, "Cancel")
        self.assertFalse(assertion.passed)


class TestRunTest(unittest.TestCase):
    def setUp(self):
        self.runner = VisualTestRunner()

    def test_run_test_all_pass(self):
        a1 = VisualAssertion(name="a", expected="x", actual="x", passed=True)
        a2 = VisualAssertion(name="b", expected="y", actual="y", passed=True)
        result = self.runner.run_test("my_test", [a1, a2])
        self.assertTrue(result.passed)
        self.assertEqual(result.test_name, "my_test")
        self.assertEqual(len(result.assertions), 2)

    def test_run_test_with_failure(self):
        a1 = VisualAssertion(name="a", expected="x", actual="x", passed=True)
        a2 = VisualAssertion(name="b", expected="y", actual="z", passed=False)
        result = self.runner.run_test("fail_test", [a1, a2])
        self.assertFalse(result.passed)

    def test_run_test_empty_assertions(self):
        result = self.runner.run_test("empty_test", [])
        self.assertTrue(result.passed)  # vacuously true


class TestResults(unittest.TestCase):
    def test_results_tracking(self):
        runner = VisualTestRunner()
        a = VisualAssertion(name="a", expected="x", actual="x", passed=True)
        runner.run_test("t1", [a])
        runner.run_test("t2", [a])
        self.assertEqual(len(runner.results()), 2)

    def test_summary_no_tests(self):
        runner = VisualTestRunner()
        self.assertIn("No visual tests", runner.summary())

    def test_summary_with_tests(self):
        runner = VisualTestRunner()
        a_pass = VisualAssertion(name="a", expected="x", actual="x", passed=True)
        a_fail = VisualAssertion(name="b", expected="y", actual="z", passed=False)
        runner.run_test("pass_test", [a_pass])
        runner.run_test("fail_test", [a_fail])
        summary = runner.summary()
        self.assertIn("2 total", summary)
        self.assertIn("1 passed", summary)
        self.assertIn("1 failed", summary)
        self.assertIn("PASS", summary)
        self.assertIn("FAIL", summary)


if __name__ == "__main__":
    unittest.main()
