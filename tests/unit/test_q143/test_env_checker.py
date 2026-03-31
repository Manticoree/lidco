"""Tests for EnvironmentChecker — Task 847."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from lidco.diagnostics.env_checker import EnvironmentChecker, EnvCheck


class TestEnvCheck(unittest.TestCase):
    def test_dataclass_fields(self):
        ec = EnvCheck(name="x", status="ok", value="v", message="m")
        self.assertEqual(ec.name, "x")
        self.assertEqual(ec.status, "ok")
        self.assertEqual(ec.value, "v")
        self.assertEqual(ec.message, "m")

    def test_none_value(self):
        ec = EnvCheck(name="x", status="error", value=None, message="missing")
        self.assertIsNone(ec.value)


class TestCheckPythonVersion(unittest.TestCase):
    def test_current_version_ok(self):
        checker = EnvironmentChecker()
        result = checker.check_python_version("3.0")
        self.assertEqual(result.status, "ok")
        self.assertIn(">=", result.message)

    def test_high_version_error(self):
        checker = EnvironmentChecker()
        result = checker.check_python_version("99.0")
        self.assertEqual(result.status, "error")
        self.assertIn("<", result.message)

    def test_exact_current_version(self):
        vi = sys.version_info
        checker = EnvironmentChecker()
        result = checker.check_python_version(f"{vi.major}.{vi.minor}.{vi.micro}")
        self.assertEqual(result.status, "ok")

    def test_value_contains_version(self):
        checker = EnvironmentChecker()
        result = checker.check_python_version("3.0")
        self.assertIn(".", result.value)


class TestCheckEnvVar(unittest.TestCase):
    def test_var_present(self):
        checker = EnvironmentChecker(_getenv=lambda n: "val123")
        result = checker.check_env_var("MY_VAR")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.value, "val123")

    def test_var_missing_required(self):
        checker = EnvironmentChecker(_getenv=lambda n: None)
        result = checker.check_env_var("MISSING", required=True)
        self.assertEqual(result.status, "error")
        self.assertIn("required", result.message)

    def test_var_missing_optional(self):
        checker = EnvironmentChecker(_getenv=lambda n: None)
        result = checker.check_env_var("OPT", required=False)
        self.assertEqual(result.status, "warning")
        self.assertIn("optional", result.message)

    def test_var_empty_string_is_missing(self):
        checker = EnvironmentChecker(_getenv=lambda n: "")
        result = checker.check_env_var("EMPTY", required=True)
        self.assertEqual(result.status, "error")


class TestCheckDirectory(unittest.TestCase):
    def test_dir_exists(self):
        checker = EnvironmentChecker(_exists=lambda p: True, _isdir=lambda p: True)
        result = checker.check_directory("/tmp/test")
        self.assertEqual(result.status, "ok")

    def test_dir_not_exists(self):
        checker = EnvironmentChecker(_exists=lambda p: False)
        result = checker.check_directory("/nope")
        self.assertEqual(result.status, "error")
        self.assertIn("does not exist", result.message)

    def test_not_a_directory(self):
        checker = EnvironmentChecker(_exists=lambda p: True, _isdir=lambda p: False)
        result = checker.check_directory("/file.txt")
        self.assertEqual(result.status, "error")
        self.assertIn("not a directory", result.message)

    def test_dir_not_writable(self):
        checker = EnvironmentChecker(
            _exists=lambda p: True,
            _isdir=lambda p: True,
            _access=lambda p, m: False,
        )
        result = checker.check_directory("/readonly", writable=True)
        self.assertEqual(result.status, "warning")
        self.assertIn("not writable", result.message)

    def test_dir_writable(self):
        checker = EnvironmentChecker(
            _exists=lambda p: True,
            _isdir=lambda p: True,
            _access=lambda p, m: True,
        )
        result = checker.check_directory("/writable", writable=True)
        self.assertEqual(result.status, "ok")
        self.assertIn("writable", result.message)


class TestAddCheck(unittest.TestCase):
    def test_custom_check_runs(self):
        checker = EnvironmentChecker()
        custom = EnvCheck("custom", "ok", "42", "all good")
        checker.add_check("custom", lambda: custom)
        results = checker.check_all()
        names = [r.name for r in results]
        self.assertIn("custom", names)

    def test_custom_check_exception(self):
        checker = EnvironmentChecker()
        checker.add_check("boom", lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        results = checker.check_all()
        boom = [r for r in results if r.name == "boom"]
        self.assertEqual(len(boom), 1)
        self.assertEqual(boom[0].status, "error")
        self.assertIn("fail", boom[0].message)


class TestCheckAll(unittest.TestCase):
    def test_includes_python_check(self):
        checker = EnvironmentChecker()
        results = checker.check_all()
        self.assertTrue(any(r.name == "python_version" for r in results))

    def test_returns_list(self):
        checker = EnvironmentChecker()
        self.assertIsInstance(checker.check_all(), list)


class TestSummary(unittest.TestCase):
    def test_summary_without_prior_check_all(self):
        checker = EnvironmentChecker()
        text = checker.summary()
        self.assertIn("Environment:", text)

    def test_summary_with_results(self):
        checker = EnvironmentChecker()
        checker.check_all()
        text = checker.summary()
        self.assertIn("[ok]", text)

    def test_summary_counts(self):
        checker = EnvironmentChecker()
        checker.add_check("warn_one", lambda: EnvCheck("warn_one", "warning", None, "w"))
        checker.check_all()
        text = checker.summary()
        self.assertIn("1 warning", text)


if __name__ == "__main__":
    unittest.main()
