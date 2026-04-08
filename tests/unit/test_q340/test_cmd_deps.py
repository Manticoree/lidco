"""Tests for CommandDependencyChecker (Q340 Task 2)."""
from __future__ import annotations

import unittest


class TestCheckDependencies(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_deps import CommandDependencyChecker
        self.c = CommandDependencyChecker()

    def test_empty_source_returns_empty(self):
        result = self.c.check_dependencies("")
        self.assertEqual(result, [])

    def test_stdlib_import_available(self):
        source = "import os\nimport sys\n"
        result = self.c.check_dependencies(source)
        statuses = [r["status"] for r in result]
        self.assertTrue(all(s == "available" for s in statuses))

    def test_missing_import_flagged(self):
        source = "import _nonexistent_pkg_xyz_abc\n"
        result = self.c.check_dependencies(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "missing")

    def test_missing_import_has_suggestion(self):
        source = "import _nonexistent_pkg_xyz_abc\n"
        result = self.c.check_dependencies(source)
        self.assertIn("suggestion", result[0])
        self.assertTrue(len(result[0]["suggestion"]) > 0)

    def test_from_import_available(self):
        source = "from os.path import join\n"
        result = self.c.check_dependencies(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "available")


class TestDetectMissingImports(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_deps import CommandDependencyChecker
        self.c = CommandDependencyChecker()

    def test_empty_source(self):
        result = self.c.detect_missing_imports("")
        self.assertEqual(result, [])

    def test_available_stdlib(self):
        source = "import json\nimport re\n"
        result = self.c.detect_missing_imports(source)
        self.assertTrue(all(r["available"] for r in result))

    def test_unavailable_module(self):
        source = "import _fake_module_zzz\n"
        result = self.c.detect_missing_imports(source)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["available"])
        self.assertEqual(result[0]["module"], "_fake_module_zzz")

    def test_line_number_correct(self):
        source = "# comment\nimport json\n"
        result = self.c.detect_missing_imports(source)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["line"], 2)


class TestValidateFallbacks(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_deps import CommandDependencyChecker
        self.c = CommandDependencyChecker()

    def test_no_try_blocks(self):
        source = "import os\n"
        result = self.c.validate_fallbacks(source)
        self.assertEqual(result, [])

    def test_correct_fallback_detected(self):
        source = (
            "try:\n"
            "    import _fake_module_xyz\n"
            "except ImportError:\n"
            "    _fake_module_xyz = None\n"
        )
        result = self.c.validate_fallbacks(source)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["has_fallback"])
        self.assertTrue(result[0]["fallback_correct"])

    def test_missing_fallback_detected(self):
        source = (
            "try:\n"
            "    import _fake_module_xyz\n"
            "except ValueError:\n"
            "    pass\n"
        )
        result = self.c.validate_fallbacks(source)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["has_fallback"])

    def test_module_name_recorded(self):
        source = (
            "try:\n"
            "    import _fake_module_xyz\n"
            "except ImportError:\n"
            "    _fake_module_xyz = None\n"
        )
        result = self.c.validate_fallbacks(source)
        self.assertIn("_fake_module_xyz", result[0]["module"])


class TestGenerateReport(unittest.TestCase):
    def setUp(self):
        from lidco.stability.cmd_deps import CommandDependencyChecker
        self.c = CommandDependencyChecker()

    def test_empty_findings(self):
        result = self.c.generate_report([])
        self.assertIn("No dependency issues", result)

    def test_report_contains_missing_marker(self):
        findings = [
            {"line": 1, "dependency": "_bad_pkg", "status": "missing", "suggestion": "install it"}
        ]
        report = self.c.generate_report(findings)
        self.assertIn("[MISSING]", report)

    def test_report_contains_ok_marker(self):
        findings = [
            {"line": 2, "dependency": "os", "status": "available", "suggestion": ""}
        ]
        report = self.c.generate_report(findings)
        self.assertIn("[OK]", report)

    def test_report_summary_line(self):
        findings = [
            {"line": 1, "dependency": "_bad", "status": "missing", "suggestion": "fix it"},
            {"line": 2, "dependency": "os", "status": "available", "suggestion": ""},
        ]
        report = self.c.generate_report(findings)
        self.assertIn("Total checked: 2", report)
        self.assertIn("Missing: 1", report)


if __name__ == "__main__":
    unittest.main()
