"""Tests for lidco.e2e_intel.failure — E2EFailureAnalyzer."""

from __future__ import annotations

import unittest

from lidco.e2e_intel.failure import (
    DOMSnapshot,
    E2EFailureAnalyzer,
    FailureCategory,
    FailureContext,
    FailureReport,
    NetworkRequest,
    RootCauseAnalysis,
    ScreenshotInfo,
)


class TestFailureCategoryEnum(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(FailureCategory.ELEMENT_NOT_FOUND.value, "element_not_found")
        self.assertEqual(FailureCategory.TIMEOUT.value, "timeout")
        self.assertEqual(FailureCategory.ASSERTION_FAILED.value, "assertion_failed")
        self.assertEqual(FailureCategory.NETWORK_ERROR.value, "network_error")
        self.assertEqual(FailureCategory.JAVASCRIPT_ERROR.value, "javascript_error")
        self.assertEqual(FailureCategory.NAVIGATION_ERROR.value, "navigation_error")
        self.assertEqual(FailureCategory.UNKNOWN.value, "unknown")


class TestNetworkRequest(unittest.TestCase):
    def test_frozen(self) -> None:
        r = NetworkRequest(url="/api", method="GET", status=200)
        with self.assertRaises(AttributeError):
            r.status = 500  # type: ignore[misc]

    def test_is_failed_by_status(self) -> None:
        r = NetworkRequest(url="/api", method="GET", status=500)
        self.assertTrue(r.is_failed)

    def test_is_failed_by_error(self) -> None:
        r = NetworkRequest(url="/api", method="GET", status=0, error="timeout")
        self.assertTrue(r.is_failed)

    def test_not_failed(self) -> None:
        r = NetworkRequest(url="/api", method="GET", status=200)
        self.assertFalse(r.is_failed)


class TestDOMSnapshot(unittest.TestCase):
    def test_frozen(self) -> None:
        d = DOMSnapshot(html="<div>", visible_text="hi")
        with self.assertRaises(AttributeError):
            d.html = ""  # type: ignore[misc]


class TestScreenshotInfo(unittest.TestCase):
    def test_frozen(self) -> None:
        s = ScreenshotInfo(path="/tmp/shot.png", width=1920, height=1080)
        with self.assertRaises(AttributeError):
            s.path = ""  # type: ignore[misc]


class TestFailureContext(unittest.TestCase):
    def test_frozen(self) -> None:
        ctx = FailureContext(test_name="t", error_message="fail")
        with self.assertRaises(AttributeError):
            ctx.test_name = "x"  # type: ignore[misc]

    def test_default_fields(self) -> None:
        ctx = FailureContext(test_name="t", error_message="e")
        self.assertEqual(ctx.stack_trace, "")
        self.assertIsNone(ctx.screenshot)
        self.assertIsNone(ctx.dom_snapshot)
        self.assertEqual(ctx.network_requests, ())
        self.assertEqual(ctx.console_logs, ())


class TestRootCauseAnalysis(unittest.TestCase):
    def test_frozen(self) -> None:
        r = RootCauseAnalysis(
            category=FailureCategory.TIMEOUT,
            confidence=0.9,
            summary="timed out",
        )
        with self.assertRaises(AttributeError):
            r.confidence = 0.1  # type: ignore[misc]


class TestE2EFailureAnalyzer(unittest.TestCase):
    def test_empty_history(self) -> None:
        a = E2EFailureAnalyzer()
        self.assertEqual(a.history, [])

    def test_record_failure_immutable_history(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(test_name="t", error_message="e")
        a.record_failure(ctx)
        self.assertEqual(len(a.history), 1)
        # Returned list is a copy
        h = a.history
        h.clear()
        self.assertEqual(len(a.history), 1)

    def test_classify_element_not_found(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(
            test_name="t", error_message="Element not found: #btn"
        )
        report = a.analyze(ctx)
        self.assertEqual(report.primary_category, FailureCategory.ELEMENT_NOT_FOUND)

    def test_classify_timeout(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(
            test_name="t", error_message="Timed out waiting for selector"
        )
        report = a.analyze(ctx)
        self.assertEqual(report.primary_category, FailureCategory.TIMEOUT)

    def test_classify_assertion(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(
            test_name="t", error_message="AssertionError: expected 5 to equal 3"
        )
        report = a.analyze(ctx)
        self.assertEqual(report.primary_category, FailureCategory.ASSERTION_FAILED)

    def test_classify_network(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(
            test_name="t", error_message="Network error: connection refused"
        )
        report = a.analyze(ctx)
        self.assertEqual(report.primary_category, FailureCategory.NETWORK_ERROR)

    def test_classify_javascript(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(
            test_name="t", error_message="Uncaught JavaScript error on page"
        )
        report = a.analyze(ctx)
        self.assertEqual(report.primary_category, FailureCategory.JAVASCRIPT_ERROR)

    def test_classify_navigation(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(
            test_name="t", error_message="Page navigation failed"
        )
        report = a.analyze(ctx)
        self.assertEqual(report.primary_category, FailureCategory.NAVIGATION_ERROR)

    def test_classify_unknown(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(test_name="t", error_message="something weird")
        report = a.analyze(ctx)
        self.assertEqual(report.primary_category, FailureCategory.UNKNOWN)

    def test_network_failure_detected(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(
            test_name="t",
            error_message="something",
            network_requests=(
                NetworkRequest(url="/api", method="POST", status=500),
            ),
        )
        report = a.analyze(ctx)
        cats = {rc.category for rc in report.root_causes}
        self.assertIn(FailureCategory.NETWORK_ERROR, cats)

    def test_dom_error_messages_detected(self) -> None:
        a = E2EFailureAnalyzer()
        dom = DOMSnapshot(error_messages=("Error: 500 Internal",))
        ctx = FailureContext(
            test_name="t", error_message="something", dom_snapshot=dom
        )
        report = a.analyze(ctx)
        cats = {rc.category for rc in report.root_causes}
        self.assertIn(FailureCategory.JAVASCRIPT_ERROR, cats)

    def test_flaky_detection(self) -> None:
        a = E2EFailureAnalyzer(flaky_threshold=2)
        ctx = FailureContext(test_name="flaky_test", error_message="fail")
        # Record twice to meet threshold
        a.record_failure(ctx)
        a.record_failure(ctx)
        report = a.analyze(ctx)
        self.assertTrue(report.is_flaky)

    def test_not_flaky_below_threshold(self) -> None:
        a = E2EFailureAnalyzer(flaky_threshold=3)
        ctx = FailureContext(test_name="t", error_message="fail")
        report = a.analyze(ctx)
        self.assertFalse(report.is_flaky)

    def test_similar_failures_found(self) -> None:
        a = E2EFailureAnalyzer()
        # Record a previous failure with same error
        a.record_failure(
            FailureContext(test_name="prev_test", error_message="Element not found")
        )
        ctx = FailureContext(test_name="new_test", error_message="Element not found")
        report = a.analyze(ctx)
        self.assertIn("prev_test", report.similar_failures)

    def test_analyze_records_to_history(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(test_name="t", error_message="fail")
        a.analyze(ctx)
        self.assertEqual(len(a.history), 1)

    def test_root_causes_sorted_by_confidence(self) -> None:
        a = E2EFailureAnalyzer()
        ctx = FailureContext(
            test_name="t",
            error_message="something",
            network_requests=(
                NetworkRequest(url="/api", method="GET", status=500),
            ),
        )
        report = a.analyze(ctx)
        confidences = [rc.confidence for rc in report.root_causes]
        self.assertEqual(confidences, sorted(confidences, reverse=True))


if __name__ == "__main__":
    unittest.main()
