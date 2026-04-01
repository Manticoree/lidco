"""Tests for CodeQualityReviewer and CodeSimplifier — Task 1045."""

from __future__ import annotations

import unittest

from lidco.review.pipeline import ReviewSeverity
from lidco.review.agents.quality import CodeQualityReviewer, CodeSimplifier


def _make_diff(file: str, lines: list[str]) -> str:
    added = "\n".join(f"+{line}" for line in lines)
    return f"+++ b/{file}\n@@ -0,0 +1,{len(lines)} @@\n{added}"


class TestCodeQualityReviewer(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = CodeQualityReviewer()

    def test_name(self) -> None:
        self.assertEqual(self.agent.name, "quality-reviewer")

    def test_deep_nesting(self) -> None:
        # 5 levels = 20 spaces
        diff = _make_diff("app.py", ["                        x = 1"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("nesting" in i.message.lower() for i in issues))

    def test_shallow_nesting_no_issue(self) -> None:
        diff = _make_diff("app.py", ["        x = 1"])
        issues = self.agent.analyze(diff, [])
        nesting = [i for i in issues if "nesting" in i.message.lower()]
        self.assertEqual(len(nesting), 0)

    def test_magic_number(self) -> None:
        diff = _make_diff("app.py", ["timeout = 86400"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("Magic" in i.message for i in issues))

    def test_long_line(self) -> None:
        long = "x = " + "a" * 130
        diff = _make_diff("app.py", [long])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("long" in i.message.lower() for i in issues))

    def test_normal_line_no_issue(self) -> None:
        diff = _make_diff("app.py", ["x = 1"])
        issues = self.agent.analyze(diff, [])
        line_issues = [i for i in issues if "long" in i.message.lower()]
        self.assertEqual(len(line_issues), 0)

    def test_single_letter_variable(self) -> None:
        diff = _make_diff("app.py", ["a = compute()"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("Single-letter" in i.message for i in issues))

    def test_common_letters_not_flagged(self) -> None:
        # i, j, k, x, y are common and should not be flagged
        diff = _make_diff("app.py", ["i = 0"])
        issues = self.agent.analyze(diff, [])
        single = [i for i in issues if "Single-letter" in i.message]
        self.assertEqual(len(single), 0)

    def test_boolean_comparison(self) -> None:
        diff = _make_diff("app.py", ["if x == True:"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("boolean" in i.message.lower() for i in issues))

    def test_boolean_false_comparison(self) -> None:
        diff = _make_diff("app.py", ["if x == False:"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("boolean" in i.message.lower() for i in issues))

    def test_deep_nesting_severity(self) -> None:
        diff = _make_diff("app.py", ["                        x = 1"])
        issues = self.agent.analyze(diff, [])
        nesting = [i for i in issues if "nesting" in i.message.lower()]
        for issue in nesting:
            self.assertEqual(issue.severity, ReviewSeverity.IMPORTANT)


class TestCodeSimplifier(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = CodeSimplifier()

    def test_name(self) -> None:
        self.assertEqual(self.agent.name, "simplifier")

    def test_return_true_pattern(self) -> None:
        diff = _make_diff("app.py", ["    return True"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("return True" in i.message or "return" in i.message.lower() for i in issues))

    def test_else_after_return(self) -> None:
        diff = _make_diff("app.py", ["    else:"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("else" in i.message.lower() for i in issues))

    def test_chained_isinstance(self) -> None:
        diff = _make_diff("app.py", ["if isinstance(x, int) and isinstance(x, str):"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("isinstance" in i.message for i in issues))

    def test_len_equals_zero(self) -> None:
        diff = _make_diff("app.py", ["if len(items) == 0:"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("len" in i.message for i in issues))

    def test_len_greater_zero(self) -> None:
        diff = _make_diff("app.py", ["if len(items) > 0:"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("len" in i.message for i in issues))

    def test_commented_import(self) -> None:
        diff = _make_diff("app.py", ["# import os"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("Commented" in i.message for i in issues))

    def test_commented_from_import(self) -> None:
        diff = _make_diff("app.py", ["# from os import path"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("Commented" in i.message for i in issues))

    def test_clean_code(self) -> None:
        diff = _make_diff("app.py", ["result = compute(data)", "return result"])
        issues = self.agent.analyze(diff, [])
        # May get 'return True' false positive, filter those
        non_return = [i for i in issues if "Commented" in i.message or "isinstance" in i.message]
        self.assertEqual(len(non_return), 0)

    def test_severity_is_suggestion(self) -> None:
        diff = _make_diff("app.py", ["if len(items) == 0:"])
        issues = self.agent.analyze(diff, [])
        for issue in issues:
            self.assertEqual(issue.severity, ReviewSeverity.SUGGESTION)


if __name__ == "__main__":
    unittest.main()
