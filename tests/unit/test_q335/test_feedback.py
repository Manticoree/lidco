"""Tests for lidco.mentor.feedback — Feedback Generator."""

from __future__ import annotations

import unittest

from lidco.mentor.feedback import (
    ActionItem,
    Category,
    FeedbackGenerator,
    FeedbackReport,
    ImprovementArea,
    Severity,
    Strength,
)


class TestFeedbackReport(unittest.TestCase):
    """Tests for FeedbackReport properties."""

    def test_counts(self) -> None:
        report = FeedbackReport(title="Test")
        report.strengths = [Strength("Good", category=Category.READABILITY)]
        report.improvements = [
            ImprovementArea("Fix", severity=Severity.CRITICAL),
            ImprovementArea("Improve", severity=Severity.SUGGESTION),
        ]
        self.assertEqual(report.strength_count, 1)
        self.assertEqual(report.improvement_count, 2)
        self.assertEqual(report.critical_count, 1)

    def test_label_excellent(self) -> None:
        report = FeedbackReport(title="T", overall_score=9.0)
        self.assertEqual(report.label, "excellent")

    def test_label_good(self) -> None:
        report = FeedbackReport(title="T", overall_score=7.0)
        self.assertEqual(report.label, "good")

    def test_label_needs_improvement(self) -> None:
        report = FeedbackReport(title="T", overall_score=5.0)
        self.assertEqual(report.label, "needs improvement")

    def test_label_significant_issues(self) -> None:
        report = FeedbackReport(title="T", overall_score=2.0)
        self.assertEqual(report.label, "significant issues")


class TestFeedbackGenerator(unittest.TestCase):
    """Tests for FeedbackGenerator."""

    def test_analyze_empty_code(self) -> None:
        gen = FeedbackGenerator()
        report = gen.analyze_code("")
        self.assertEqual(report.overall_score, 10.0)

    def test_analyze_good_code(self) -> None:
        gen = FeedbackGenerator()
        code = '''
def greet(name: str) -> str:
    """Return a greeting."""
    try:
        return f"Hello, {name}"
    except Exception as e:
        raise ValueError(str(e))
'''
        report = gen.analyze_code(code, title="Greet Review")
        self.assertEqual(report.title, "Greet Review")
        self.assertGreater(report.strength_count, 0)

    def test_finds_docstring_strength(self) -> None:
        gen = FeedbackGenerator()
        code = '"""Module doc."""\ndef foo():\n    pass'
        report = gen.analyze_code(code)
        descs = [s.description for s in report.strengths]
        self.assertTrue(any("docstring" in d.lower() for d in descs))

    def test_finds_type_hint_strength(self) -> None:
        gen = FeedbackGenerator()
        code = "def foo(x: int) -> str:\n    return str(x)"
        report = gen.analyze_code(code)
        descs = [s.description for s in report.strengths]
        self.assertTrue(any("type hint" in d.lower() for d in descs))

    def test_finds_error_handling_strength(self) -> None:
        gen = FeedbackGenerator()
        code = "try:\n    x = 1\nexcept ValueError:\n    pass"
        report = gen.analyze_code(code)
        descs = [s.description for s in report.strengths]
        self.assertTrue(any("error handling" in d.lower() for d in descs))

    def test_finds_test_strength(self) -> None:
        gen = FeedbackGenerator()
        code = "def test_foo():\n    assert True"
        report = gen.analyze_code(code)
        descs = [s.description for s in report.strengths]
        self.assertTrue(any("test" in d.lower() for d in descs))

    def test_finds_constant_strength(self) -> None:
        gen = FeedbackGenerator()
        code = "MAX_RETRIES = 3\ndef foo():\n    pass"
        report = gen.analyze_code(code)
        descs = [s.description for s in report.strengths]
        self.assertTrue(any("constant" in d.lower() for d in descs))

    def test_detects_bare_except(self) -> None:
        gen = FeedbackGenerator()
        code = "try:\n    x = 1\nexcept:\n    pass"
        report = gen.analyze_code(code)
        descs = [i.description for i in report.improvements]
        self.assertTrue(any("bare except" in d.lower() for d in descs))

    def test_detects_print_statement(self) -> None:
        gen = FeedbackGenerator()
        code = 'print("debug")'
        report = gen.analyze_code(code)
        descs = [i.description for i in report.improvements]
        self.assertTrue(any("print" in d.lower() for d in descs))

    def test_detects_global_statement(self) -> None:
        gen = FeedbackGenerator()
        code = "def foo():\n    global x\n    x = 1"
        report = gen.analyze_code(code)
        descs = [i.description for i in report.improvements]
        self.assertTrue(any("global" in d.lower() for d in descs))

    def test_score_clamped(self) -> None:
        gen = FeedbackGenerator()
        # Code with many issues should not go below 0
        code = "\n".join(["except:" for _ in range(20)])
        report = gen.analyze_code(code)
        self.assertGreaterEqual(report.overall_score, 0.0)
        self.assertLessEqual(report.overall_score, 10.0)

    def test_action_items_generated(self) -> None:
        gen = FeedbackGenerator()
        code = "except:\n    pass\nglobal x"
        report = gen.analyze_code(code)
        self.assertGreater(len(report.action_items), 0)

    def test_action_items_sorted_by_priority(self) -> None:
        gen = FeedbackGenerator()
        code = "except:\n    pass\nglobal x\nprint('hi')"
        report = gen.analyze_code(code)
        if len(report.action_items) > 1:
            priorities = [a.priority for a in report.action_items]
            self.assertEqual(priorities, sorted(priorities))

    def test_summary_generated(self) -> None:
        gen = FeedbackGenerator()
        code = '"""Doc."""\ndef foo() -> int:\n    return 1'
        report = gen.analyze_code(code)
        self.assertIsInstance(report.summary, str)
        self.assertTrue(len(report.summary) > 0)

    def test_add_custom_check(self) -> None:
        gen = FeedbackGenerator()
        gen.add_check("fixme", r"FIXME", "FIXME found", "documentation")
        code = "# FIXME: broken"
        report = gen.analyze_code(code)
        descs = [i.description for i in report.improvements]
        self.assertTrue(any("FIXME" in d for d in descs))

    def test_remove_check(self) -> None:
        gen = FeedbackGenerator()
        self.assertTrue(gen.remove_check("print_statement"))
        code = 'print("hi")'
        report = gen.analyze_code(code)
        descs = [i.description for i in report.improvements]
        self.assertFalse(any("print" in d.lower() for d in descs))

    def test_remove_check_nonexistent(self) -> None:
        gen = FeedbackGenerator()
        self.assertFalse(gen.remove_check("nonexistent"))

    def test_deep_nesting_detection(self) -> None:
        gen = FeedbackGenerator()
        # 5 levels of nesting = 20 spaces
        code = "if True:\n    if True:\n        if True:\n            if True:\n                if True:\n                    x = 1"
        report = gen.analyze_code(code)
        descs = [i.description for i in report.improvements]
        self.assertTrue(any("nesting" in d.lower() for d in descs))


if __name__ == "__main__":
    unittest.main()
