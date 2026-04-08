"""Tests for src/lidco/onboard/setup.py — SetupAssistant."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from lidco.onboard.setup import (
    CheckResult,
    CheckStatus,
    SetupAssistant,
    SetupReport,
    SetupStep,
)


class TestCheckStatus(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(CheckStatus.PASS.value, "pass")
        self.assertEqual(CheckStatus.FAIL.value, "fail")
        self.assertEqual(CheckStatus.WARN.value, "warn")
        self.assertEqual(CheckStatus.SKIP.value, "skip")


class TestCheckResult(unittest.TestCase):
    def test_defaults(self) -> None:
        r = CheckResult(name="test", status=CheckStatus.PASS)
        self.assertEqual(r.message, "")
        self.assertEqual(r.fix_hint, "")

    def test_frozen(self) -> None:
        r = CheckResult(name="a", status=CheckStatus.PASS)
        with self.assertRaises(AttributeError):
            r.name = "b"  # type: ignore[misc]


class TestSetupStep(unittest.TestCase):
    def test_defaults(self) -> None:
        s = SetupStep(name="install", description="Install deps")
        self.assertEqual(s.command, "")
        self.assertEqual(s.check_command, "")
        self.assertTrue(s.required)
        self.assertEqual(s.order, 0)


class TestSetupReport(unittest.TestCase):
    def test_empty(self) -> None:
        r = SetupReport()
        self.assertEqual(r.passed, 0)
        self.assertEqual(r.failed, 0)
        self.assertEqual(r.warnings, 0)
        self.assertTrue(r.all_passed)

    def test_mixed(self) -> None:
        r = SetupReport(results=[
            CheckResult(name="a", status=CheckStatus.PASS),
            CheckResult(name="b", status=CheckStatus.FAIL),
            CheckResult(name="c", status=CheckStatus.WARN),
        ])
        self.assertEqual(r.passed, 1)
        self.assertEqual(r.failed, 1)
        self.assertEqual(r.warnings, 1)
        self.assertFalse(r.all_passed)


class TestSetupAssistant(unittest.TestCase):
    def test_root_dir(self) -> None:
        a = SetupAssistant(root_dir="/foo")
        self.assertEqual(a.root_dir, "/foo")

    def test_add_step(self) -> None:
        a = SetupAssistant()
        a.add_step(SetupStep(name="s1", description="Step 1"))
        self.assertEqual(len(a.steps), 1)

    def test_add_steps(self) -> None:
        a = SetupAssistant()
        a.add_steps([
            SetupStep(name="s1", description="Step 1"),
            SetupStep(name="s2", description="Step 2"),
        ])
        self.assertEqual(len(a.steps), 2)

    def test_register_and_run_check(self) -> None:
        a = SetupAssistant()
        a.register_check("ok", lambda: CheckResult(name="ok", status=CheckStatus.PASS, message="fine"))
        result = a.check_dependency("ok")
        self.assertEqual(result.status, CheckStatus.PASS)

    def test_check_dependency_unregistered(self) -> None:
        a = SetupAssistant()
        result = a.check_dependency("missing")
        self.assertEqual(result.status, CheckStatus.SKIP)

    def test_check_dependency_raises(self) -> None:
        a = SetupAssistant()
        a.register_check("bad", lambda: (_ for _ in ()).throw(RuntimeError("boom")))  # type: ignore[func-returns-value]

        def _boom() -> CheckResult:
            raise RuntimeError("boom")

        a.register_check("bad", _boom)
        result = a.check_dependency("bad")
        self.assertEqual(result.status, CheckStatus.FAIL)
        self.assertIn("boom", result.message)

    @mock.patch("lidco.onboard.setup.shutil.which", return_value="/usr/bin/python")
    def test_check_command_exists_found(self, mock_which: mock.MagicMock) -> None:
        a = SetupAssistant()
        result = a.check_command_exists("python")
        self.assertEqual(result.status, CheckStatus.PASS)
        self.assertIn("/usr/bin/python", result.message)

    @mock.patch("lidco.onboard.setup.shutil.which", return_value=None)
    def test_check_command_exists_not_found(self, mock_which: mock.MagicMock) -> None:
        a = SetupAssistant()
        result = a.check_command_exists("missing-cmd")
        self.assertEqual(result.status, CheckStatus.FAIL)
        self.assertIn("not found", result.message)
        self.assertTrue(len(result.fix_hint) > 0)

    def test_check_file_exists_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.txt")
            with open(path, "w") as f:
                f.write("hi")
            a = SetupAssistant(root_dir=tmpdir)
            result = a.check_file_exists("test.txt")
            self.assertEqual(result.status, CheckStatus.PASS)

    def test_check_file_exists_not_found(self) -> None:
        a = SetupAssistant(root_dir="/nonexistent")
        result = a.check_file_exists("nope.txt")
        self.assertEqual(result.status, CheckStatus.FAIL)

    def test_check_python_version(self) -> None:
        a = SetupAssistant()
        result = a.check_python_version("3.0")
        self.assertEqual(result.status, CheckStatus.PASS)

    def test_check_python_version_too_high(self) -> None:
        a = SetupAssistant()
        result = a.check_python_version("99.0")
        self.assertEqual(result.status, CheckStatus.FAIL)

    def test_run_all_checks(self) -> None:
        a = SetupAssistant()
        a.register_check("ok", lambda: CheckResult(name="ok", status=CheckStatus.PASS))
        a.register_check("bad", lambda: CheckResult(name="bad", status=CheckStatus.FAIL))
        report = a.run_all_checks()
        self.assertEqual(report.passed, 1)
        self.assertEqual(report.failed, 1)

    def test_config_template(self) -> None:
        a = SetupAssistant()
        a.add_config_template("env", "HOST={{host}}\nPORT={{port}}")
        self.assertEqual(a.list_config_templates(), ["env"])
        result = a.generate_config("env", {"host": "localhost", "port": "8080"})
        self.assertEqual(result, "HOST=localhost\nPORT=8080")

    def test_generate_config_missing(self) -> None:
        a = SetupAssistant()
        self.assertIsNone(a.generate_config("missing"))

    def test_generate_config_no_vars(self) -> None:
        a = SetupAssistant()
        a.add_config_template("plain", "content")
        self.assertEqual(a.generate_config("plain"), "content")

    @mock.patch("lidco.onboard.setup.shutil.which", return_value="/usr/bin/git")
    def test_verify_setup(self, mock_which: mock.MagicMock) -> None:
        a = SetupAssistant()
        a.add_step(SetupStep(name="git", description="Git", check_command="git --version"))
        report = a.verify_setup()
        found = [r for r in report.results if r.name == "step:git"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].status, CheckStatus.PASS)

    def test_summary_ready(self) -> None:
        a = SetupAssistant()
        s = a.summary()
        self.assertIn("READY", s)

    def test_summary_needs_attention(self) -> None:
        a = SetupAssistant()
        a.register_check("fail", lambda: CheckResult(name="fail", status=CheckStatus.FAIL, message="broken"))
        s = a.summary()
        self.assertIn("NEEDS ATTENTION", s)


if __name__ == "__main__":
    unittest.main()
