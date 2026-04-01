"""Tests for CommentAnalyzer and PRTestAnalyzer — Task 1043."""

from __future__ import annotations

import unittest

from lidco.review.pipeline import ReviewSeverity
from lidco.review.agents.comment_analyzer import CommentAnalyzer, PRTestAnalyzer


def _make_diff(file: str, lines: list[str]) -> str:
    """Helper to create a minimal unified diff."""
    added = "\n".join(f"+{line}" for line in lines)
    return f"+++ b/{file}\n@@ -0,0 +1,{len(lines)} @@\n{added}"


class TestCommentAnalyzer(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = CommentAnalyzer()

    def test_name(self) -> None:
        self.assertEqual(self.agent.name, "comment-analyzer")

    def test_todo_without_issue(self) -> None:
        diff = _make_diff("app.py", ["# TODO fix later"])
        issues = self.agent.analyze(diff, [])
        msgs = [i.message for i in issues]
        self.assertTrue(any("TODO" in m for m in msgs))

    def test_todo_with_issue_no_flag(self) -> None:
        diff = _make_diff("app.py", ["# TODO(#123): fix later"])
        issues = self.agent.analyze(diff, [])
        todo_issues = [i for i in issues if "TODO" in i.message and "without" in i.message]
        self.assertEqual(len(todo_issues), 0)

    def test_fixme_detected(self) -> None:
        diff = _make_diff("app.py", ["# FIXME: broken"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("FIXME" in i.message or "Stale" in i.message for i in issues))

    def test_hack_detected(self) -> None:
        diff = _make_diff("app.py", ["# HACK: workaround"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("HACK" in i.message or "Stale" in i.message for i in issues))

    def test_xxx_detected(self) -> None:
        diff = _make_diff("app.py", ["# XXX: check this"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("XXX" in i.message or "Stale" in i.message for i in issues))

    def test_empty_docstring(self) -> None:
        diff = _make_diff("app.py", ['    """"""'])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any("docstring" in i.category for i in issues))

    def test_clean_code_no_issues(self) -> None:
        diff = _make_diff("app.py", ["x = 1", "y = 2"])
        issues = self.agent.analyze(diff, [])
        self.assertEqual(len(issues), 0)

    def test_severity_is_suggestion_for_todo(self) -> None:
        diff = _make_diff("app.py", ["# TODO: no ticket"])
        issues = self.agent.analyze(diff, [])
        todo_issues = [i for i in issues if "TODO" in i.message]
        for issue in todo_issues:
            self.assertEqual(issue.severity, ReviewSeverity.SUGGESTION)

    def test_severity_is_important_for_fixme(self) -> None:
        diff = _make_diff("app.py", ["# FIXME: needs work"])
        issues = self.agent.analyze(diff, [])
        fixme_issues = [i for i in issues if "Stale" in i.message]
        for issue in fixme_issues:
            self.assertEqual(issue.severity, ReviewSeverity.IMPORTANT)

    def test_file_and_line_tracked(self) -> None:
        diff = _make_diff("mymod.py", ["# TODO: fix"])
        issues = self.agent.analyze(diff, [])
        self.assertTrue(any(i.file == "mymod.py" for i in issues))
        self.assertTrue(any(i.line > 0 for i in issues))


class TestPRTestAnalyzer(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = PRTestAnalyzer()

    def test_name(self) -> None:
        self.assertEqual(self.agent.name, "test-analyzer")

    def test_source_without_test_file(self) -> None:
        issues = self.agent.analyze("", ["src/foo.py"])
        self.assertTrue(any("no corresponding test" in i.message for i in issues))

    def test_source_with_test_file_no_issue(self) -> None:
        issues = self.agent.analyze("", ["src/foo.py", "tests/test_foo.py"])
        missing = [i for i in issues if "no corresponding test" in i.message]
        self.assertEqual(len(missing), 0)

    def test_new_public_function_flagged(self) -> None:
        diff = _make_diff("src/utils.py", ["def compute(x):", "    return x * 2"])
        issues = self.agent.analyze(diff, ["src/utils.py"])
        self.assertTrue(any("compute" in i.message for i in issues))

    def test_private_function_not_flagged(self) -> None:
        diff = _make_diff("src/utils.py", ["def _helper(x):", "    return x"])
        issues = self.agent.analyze(diff, ["src/utils.py"])
        helper_issues = [i for i in issues if "_helper" in i.message]
        self.assertEqual(len(helper_issues), 0)

    def test_test_quality_pass_only(self) -> None:
        diff = _make_diff("tests/test_foo.py", ["def test_something():", "    pass"])
        issues = self.agent.analyze(diff, ["tests/test_foo.py"])
        self.assertTrue(any("pass" in i.message.lower() for i in issues))

    def test_non_python_files_ignored(self) -> None:
        issues = self.agent.analyze("", ["README.md", "config.json"])
        self.assertEqual(len(issues), 0)

    def test_severity_for_missing_tests(self) -> None:
        issues = self.agent.analyze("", ["src/foo.py"])
        for issue in issues:
            if "no corresponding test" in issue.message:
                self.assertEqual(issue.severity, ReviewSeverity.IMPORTANT)


if __name__ == "__main__":
    unittest.main()
