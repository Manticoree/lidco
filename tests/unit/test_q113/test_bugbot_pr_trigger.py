"""Tests for BugBotPRTrigger (Task 697)."""
import unittest
from unittest.mock import MagicMock

from lidco.review.bugbot_pr_trigger import (
    BugBotFinding,
    BugBotPRTrigger,
    BugSeverity,
    PREvent,
)


class TestBugSeverityEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(BugSeverity.LOW.value, "low")
        self.assertEqual(BugSeverity.MEDIUM.value, "medium")
        self.assertEqual(BugSeverity.HIGH.value, "high")
        self.assertEqual(BugSeverity.CRITICAL.value, "critical")


class TestPREvent(unittest.TestCase):
    def test_creation(self):
        ev = PREvent(pr_number=42, repo="owner/repo", diff="some diff")
        self.assertEqual(ev.pr_number, 42)
        self.assertEqual(ev.repo, "owner/repo")
        self.assertEqual(ev.diff, "some diff")
        self.assertEqual(ev.branch, "main")

    def test_custom_branch(self):
        ev = PREvent(pr_number=1, repo="r", diff="d", branch="feature")
        self.assertEqual(ev.branch, "feature")


class TestBugBotFinding(unittest.TestCase):
    def test_creation(self):
        f = BugBotFinding(file="a.py", line=10, severity=BugSeverity.HIGH, message="bad", rule_id="r1")
        self.assertEqual(f.file, "a.py")
        self.assertIsNone(f.suggested_fix)

    def test_with_suggested_fix(self):
        f = BugBotFinding(file="b.py", line=5, severity=BugSeverity.LOW, message="m", rule_id="r2", suggested_fix="fix it")
        self.assertEqual(f.suggested_fix, "fix it")


class TestParseDiff(unittest.TestCase):
    def setUp(self):
        self.trigger = BugBotPRTrigger()

    def test_empty_diff(self):
        result = self.trigger.parse_diff("")
        self.assertEqual(result, {})

    def test_single_file_diff(self):
        diff = (
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,3 +1,4 @@\n"
            " existing\n"
            "+new_line\n"
            " more\n"
        )
        result = self.trigger.parse_diff(diff)
        self.assertIn("foo.py", result)
        self.assertEqual(result["foo.py"], ["new_line"])

    def test_multi_file_diff(self):
        diff = (
            "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n+line_a\n"
            "--- a/b.py\n+++ b/b.py\n@@ -1 +1 @@\n+line_b\n"
        )
        result = self.trigger.parse_diff(diff)
        self.assertIn("a.py", result)
        self.assertIn("b.py", result)

    def test_ignores_removed_lines(self):
        diff = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n"
        result = self.trigger.parse_diff(diff)
        self.assertEqual(result["f.py"], ["new"])

    def test_dev_null_ignored(self):
        diff = "+++ /dev/null\n+some line\n"
        result = self.trigger.parse_diff(diff)
        self.assertEqual(result, {})


class TestHeuristicScan(unittest.TestCase):
    def setUp(self):
        self.trigger = BugBotPRTrigger()

    def _event(self, diff: str) -> PREvent:
        return PREvent(pr_number=1, repo="r", diff=diff)

    def test_detects_todo(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+# TODO fix this\n"
        findings = self.trigger.process_pr_event(self._event(diff))
        todos = [f for f in findings if f.rule_id == "todo_fixme"]
        self.assertTrue(len(todos) >= 1)
        self.assertEqual(todos[0].severity, BugSeverity.LOW)

    def test_detects_fixme(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+# FIXME later\n"
        findings = self.trigger.process_pr_event(self._event(diff))
        self.assertTrue(any(f.rule_id == "todo_fixme" for f in findings))

    def test_detects_bare_except(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+except:\n"
        findings = self.trigger.process_pr_event(self._event(diff))
        bare = [f for f in findings if f.rule_id == "bare_except"]
        self.assertTrue(len(bare) >= 1)
        self.assertEqual(bare[0].severity, BugSeverity.MEDIUM)

    def test_detects_eval(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+result = eval(expr)\n"
        findings = self.trigger.process_pr_event(self._event(diff))
        evals = [f for f in findings if f.rule_id == "eval_usage"]
        self.assertTrue(len(evals) >= 1)
        self.assertEqual(evals[0].severity, BugSeverity.HIGH)

    def test_detects_hardcoded_password(self):
        diff = '--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+password = "hunter2"\n'
        findings = self.trigger.process_pr_event(self._event(diff))
        secrets = [f for f in findings if f.rule_id == "hardcoded_secret"]
        self.assertTrue(len(secrets) >= 1)
        self.assertEqual(secrets[0].severity, BugSeverity.CRITICAL)

    def test_detects_hardcoded_secret(self):
        diff = '--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+secret = "abc123"\n'
        findings = self.trigger.process_pr_event(self._event(diff))
        self.assertTrue(any(f.rule_id == "hardcoded_secret" for f in findings))

    def test_no_findings_on_clean_diff(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+x = 42\n"
        findings = self.trigger.process_pr_event(self._event(diff))
        self.assertEqual(findings, [])

    def test_severity_sort_order(self):
        diff = (
            "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n"
            "+# TODO fix\n"
            "+except:\n"
            "+eval(x)\n"
            '+password = "p"\n'
        )
        findings = self.trigger.process_pr_event(self._event(diff))
        severities = [f.severity for f in findings]
        self.assertEqual(severities[0], BugSeverity.CRITICAL)

    def test_deduplication(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+except:\n"
        # With bugbot_analyzer that also finds bare_except
        analyzer = MagicMock()
        report = MagicMock()
        report.file = "x.py"
        report.line = 1
        report.kind = "bare_except"
        report.message = "bare except"
        report.severity = "warning"
        analyzer.analyze.return_value = [report]
        trigger = BugBotPRTrigger(bugbot_analyzer=analyzer)
        findings = trigger.process_pr_event(self._event(diff))
        bare = [f for f in findings if f.rule_id == "bare_except"]
        # Should be deduplicated to 1
        self.assertEqual(len(bare), 1)


class TestWithAnalyzer(unittest.TestCase):
    def test_uses_injected_analyzer(self):
        analyzer = MagicMock()
        report = MagicMock()
        report.file = "test.py"
        report.line = 5
        report.kind = "mutable_default"
        report.message = "Mutable default"
        report.severity = "warning"
        analyzer.analyze.return_value = [report]
        trigger = BugBotPRTrigger(bugbot_analyzer=analyzer)
        ev = PREvent(pr_number=1, repo="r", diff="--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n+x = 1\n")
        findings = trigger.process_pr_event(ev)
        self.assertTrue(any(f.rule_id == "mutable_default" for f in findings))

    def test_analyzer_exception_handled(self):
        analyzer = MagicMock()
        analyzer.analyze.side_effect = RuntimeError("boom")
        trigger = BugBotPRTrigger(bugbot_analyzer=analyzer)
        ev = PREvent(pr_number=1, repo="r", diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+x = 1\n")
        findings = trigger.process_pr_event(ev)
        # Should still work (heuristic scan)
        self.assertIsInstance(findings, list)


class TestWithReviewer(unittest.TestCase):
    def test_uses_injected_reviewer(self):
        reviewer = MagicMock()
        comment = MagicMock()
        comment.path = "r.py"
        comment.line = 3
        comment.severity = "critical"
        comment.body = "Critical issue"
        comment.suggestion = "fix it"
        result = MagicMock()
        result.comments = [comment]
        reviewer.review.return_value = result
        trigger = BugBotPRTrigger(pr_reviewer=reviewer)
        ev = PREvent(pr_number=1, repo="r", diff="--- a/r.py\n+++ b/r.py\n@@ -1 +1 @@\n+x = 1\n")
        findings = trigger.process_pr_event(ev)
        self.assertTrue(any(f.rule_id == "pr_review" for f in findings))

    def test_reviewer_exception_handled(self):
        reviewer = MagicMock()
        reviewer.review.side_effect = RuntimeError("fail")
        trigger = BugBotPRTrigger(pr_reviewer=reviewer)
        ev = PREvent(pr_number=1, repo="r", diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+x = 1\n")
        findings = trigger.process_pr_event(ev)
        self.assertIsInstance(findings, list)


class TestSeverityMapping(unittest.TestCase):
    def test_map_severity(self):
        self.assertEqual(BugBotPRTrigger._map_severity("error"), BugSeverity.HIGH)
        self.assertEqual(BugBotPRTrigger._map_severity("warning"), BugSeverity.MEDIUM)
        self.assertEqual(BugBotPRTrigger._map_severity("info"), BugSeverity.LOW)
        self.assertEqual(BugBotPRTrigger._map_severity("unknown"), BugSeverity.LOW)

    def test_map_reviewer_severity(self):
        self.assertEqual(BugBotPRTrigger._map_reviewer_severity("critical"), BugSeverity.CRITICAL)
        self.assertEqual(BugBotPRTrigger._map_reviewer_severity("warning"), BugSeverity.MEDIUM)
        self.assertEqual(BugBotPRTrigger._map_reviewer_severity("suggestion"), BugSeverity.LOW)
        self.assertEqual(BugBotPRTrigger._map_reviewer_severity("other"), BugSeverity.LOW)


if __name__ == "__main__":
    unittest.main()
