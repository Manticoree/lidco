"""Tests for UltraReviewer (Q238)."""
from __future__ import annotations

import unittest

from lidco.modes.ultra_reviewer import (
    Perspective,
    ReviewFinding,
    UltraReview,
    UltraReviewer,
)


class TestPerspective(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Perspective.SECURITY.value, "security")
        self.assertEqual(Perspective.SIMPLIFICATION.value, "simplification")

    def test_all_perspectives(self):
        self.assertEqual(len(Perspective), 6)


class TestReviewFinding(unittest.TestCase):
    def test_frozen(self):
        f = ReviewFinding(perspective=Perspective.SECURITY)
        with self.assertRaises(AttributeError):
            f.message = "x"  # type: ignore[misc]

    def test_defaults(self):
        f = ReviewFinding(perspective=Perspective.LOGIC)
        self.assertEqual(f.severity, "medium")
        self.assertEqual(f.line, 0)


class TestUltraReview(unittest.TestCase):
    def test_frozen(self):
        r = UltraReview()
        with self.assertRaises(AttributeError):
            r.source_lines = 10  # type: ignore[misc]


class TestReviewSecurity(unittest.TestCase):
    def setUp(self):
        self.reviewer = UltraReviewer()

    def test_detect_eval(self):
        findings = self.reviewer.review_security("x = eval(input())")
        self.assertTrue(any("eval" in f.message.lower() for f in findings))

    def test_detect_exec(self):
        findings = self.reviewer.review_security("exec(code)")
        self.assertTrue(any("exec" in f.message.lower() for f in findings))

    def test_detect_hardcoded_secret(self):
        findings = self.reviewer.review_security('API_KEY = "sk-secret123"')
        self.assertTrue(any("secret" in f.message.lower() or "hardcoded" in f.message.lower() for f in findings))

    def test_clean_code(self):
        findings = self.reviewer.review_security("x = 1 + 2")
        self.assertEqual(len(findings), 0)


class TestReviewPerformance(unittest.TestCase):
    def setUp(self):
        self.reviewer = UltraReviewer()

    def test_nested_loops(self):
        code = "for a in x:\n    for b in y:\n        for c in z:\n            pass"
        findings = self.reviewer.review_performance(code)
        self.assertTrue(any("nested" in f.message.lower() for f in findings))


class TestReviewStyle(unittest.TestCase):
    def setUp(self):
        self.reviewer = UltraReviewer()

    def test_long_line(self):
        code = "x = " + "a" * 200
        findings = self.reviewer.review_style(code)
        self.assertTrue(any("120" in f.message for f in findings))


class TestReviewLogic(unittest.TestCase):
    def setUp(self):
        self.reviewer = UltraReviewer()

    def test_bare_except(self):
        code = "try:\n    pass\nexcept:\n    pass"
        findings = self.reviewer.review_logic(code)
        self.assertTrue(any("bare except" in f.message.lower() for f in findings))

    def test_always_true(self):
        code = "if True:\n    pass"
        findings = self.reviewer.review_logic(code)
        self.assertTrue(any("always-true" in f.message.lower() for f in findings))


class TestReviewTests(unittest.TestCase):
    def setUp(self):
        self.reviewer = UltraReviewer()

    def test_missing_assertions(self):
        code = "def test_foo():\n    x = 1"
        findings = self.reviewer.review_tests(code)
        self.assertTrue(any("assertion" in f.message.lower() for f in findings))


class TestReviewFull(unittest.TestCase):
    def setUp(self):
        self.reviewer = UltraReviewer()

    def test_full_review(self):
        code = "x = eval(input())\nexcept:\n    pass"
        review = self.reviewer.review(code)
        self.assertIsInstance(review, UltraReview)
        self.assertTrue(len(review.findings) > 0)
        self.assertEqual(len(review.perspectives_used), 6)

    def test_summary(self):
        review = UltraReview(
            findings=(ReviewFinding(Perspective.SECURITY, "high", message="issue"),),
            perspectives_used=tuple(Perspective),
            source_lines=10,
        )
        s = self.reviewer.summary(review)
        self.assertIn("1 finding", s)
        self.assertIn("high", s)


if __name__ == "__main__":
    unittest.main()
