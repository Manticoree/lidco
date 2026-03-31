"""Tests for SecurityPatternScanner."""

from __future__ import annotations

import unittest

from lidco.review.security_scanner import (
    SecurityFinding,
    SecurityPatternScanner,
    SecurityReport,
)


class TestSecurityFinding(unittest.TestCase):
    def test_frozen(self) -> None:
        f = SecurityFinding(rule="r", file="a.py", line=1, message="m")
        with self.assertRaises(AttributeError):
            f.rule = "x"  # type: ignore[misc]

    def test_defaults(self) -> None:
        f = SecurityFinding(rule="r", file="", line=1, message="m")
        self.assertEqual(f.severity, "high")
        self.assertEqual(f.owasp, "")
        self.assertEqual(f.cwe, "")


class TestSecurityReport(unittest.TestCase):
    def test_empty(self) -> None:
        r = SecurityReport()
        self.assertEqual(r.critical_count, 0)
        self.assertEqual(r.high_count, 0)
        self.assertEqual(r.total, 0)
        self.assertIn("No security issues", r.format())

    def test_counts(self) -> None:
        r = SecurityReport(findings=[
            SecurityFinding("a", "f.py", 1, "m1", severity="critical"),
            SecurityFinding("b", "f.py", 2, "m2", severity="high"),
            SecurityFinding("c", "f.py", 3, "m3", severity="critical"),
        ])
        self.assertEqual(r.critical_count, 2)
        self.assertEqual(r.high_count, 1)
        self.assertEqual(r.total, 3)

    def test_format_owasp_cwe(self) -> None:
        r = SecurityReport(findings=[
            SecurityFinding("r", "f.py", 1, "msg", owasp="A03:2021", cwe="89"),
        ])
        text = r.format()
        self.assertIn("A03:2021", text)
        self.assertIn("CWE-89", text)


class TestSecurityPatternScanner(unittest.TestCase):
    def setUp(self) -> None:
        self.scanner = SecurityPatternScanner()

    def test_clean_code(self) -> None:
        source = "def hello():\n    return 42\n"
        report = self.scanner.scan(source)
        self.assertEqual(report.total, 0)

    def test_hardcoded_secret(self) -> None:
        source = 'api_key = "sk-proj-12345678"\n'
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("hardcoded_secret", rules)

    def test_eval_usage(self) -> None:
        source = "result = eval(user_input)\n"
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("eval_usage", rules)

    def test_exec_usage(self) -> None:
        source = "exec(code_string)\n"
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("exec_usage", rules)

    def test_pickle_load(self) -> None:
        source = "data = pickle.load(f)\n"
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("pickle_load", rules)

    def test_weak_hash(self) -> None:
        source = "h = hashlib.md5(data)\n"
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("weak_hash", rules)

    def test_debug_mode(self) -> None:
        source = "DEBUG = True\n"
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("debug_mode", rules)

    def test_cors_wildcard(self) -> None:
        source = 'Access-Control-Allow-Origin: "*"\n'
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("cors_wildcard", rules)

    def test_sql_concat(self) -> None:
        source = '''cursor.execute(f"SELECT * FROM users WHERE id={uid}")\n'''
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("sql_concat", rules)

    def test_custom_rules(self) -> None:
        scanner = SecurityPatternScanner(rules=[
            {"name": "no_telnet", "pattern": r"telnet", "message": "Telnet usage", "severity": "high"},
        ])
        report = scanner.scan("connect_telnet(host)")
        self.assertEqual(len(report.findings), 1)

    def test_add_rule(self) -> None:
        scanner = SecurityPatternScanner(rules=[])
        scanner.add_rule({"name": "test", "pattern": r"DANGEROUS", "message": "found"})
        report = scanner.scan("DANGEROUS code")
        self.assertEqual(len(report.findings), 1)

    def test_invalid_regex_skipped(self) -> None:
        scanner = SecurityPatternScanner(rules=[
            {"name": "bad", "pattern": "[invalid", "message": "m"},
        ])
        report = scanner.scan("anything")
        self.assertEqual(report.total, 0)

    def test_scan_diff(self) -> None:
        diff = (
            "+++ b/app.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+result = eval(data)\n"
            "+x = 1\n"
        )
        report = self.scanner.scan_diff(diff)
        rules = [f.rule for f in report.findings]
        self.assertIn("eval_usage", rules)

    def test_scan_diff_ignores_removed(self) -> None:
        diff = (
            "+++ b/app.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-result = eval(data)\n"
            "+result = safe_parse(data)\n"
        )
        report = self.scanner.scan_diff(diff)
        rules = [f.rule for f in report.findings]
        self.assertNotIn("eval_usage", rules)

    def test_scan_diff_line_numbers(self) -> None:
        diff = (
            "+++ b/app.py\n"
            "@@ -0,0 +5,1 @@\n"
            "+result = eval(data)\n"
        )
        report = self.scanner.scan_diff(diff)
        for f in report.findings:
            if f.rule == "eval_usage":
                self.assertEqual(f.line, 5)

    def test_filename_in_findings(self) -> None:
        report = self.scanner.scan("result = eval(x)", filename="app.py")
        self.assertTrue(any(f.file == "app.py" for f in report.findings))

    def test_rules_property(self) -> None:
        rules = self.scanner.rules
        self.assertIsInstance(rules, list)
        self.assertTrue(len(rules) > 0)

    def test_assert_detected(self) -> None:
        source = "    assert x > 0\n"
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("assert_in_production", rules)

    def test_temp_file(self) -> None:
        source = "f = tempfile.mktemp()\n"
        report = self.scanner.scan(source)
        rules = [f.rule for f in report.findings]
        self.assertIn("temp_file_insecure", rules)

    def test_owasp_attached(self) -> None:
        source = "result = eval(data)\n"
        report = self.scanner.scan(source)
        finding = next(f for f in report.findings if f.rule == "eval_usage")
        self.assertNotEqual(finding.owasp, "")
        self.assertNotEqual(finding.cwe, "")


if __name__ == "__main__":
    unittest.main()
