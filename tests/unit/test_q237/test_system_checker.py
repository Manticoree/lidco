"""Tests for src/lidco/doctor/system_checker.py."""
from __future__ import annotations

import unittest
from collections import namedtuple
from unittest.mock import patch

from lidco.doctor.system_checker import CheckResult, CheckStatus, SystemChecker


class TestCheckPython(unittest.TestCase):
    def test_pass_310(self):
        vi = namedtuple("vi", "major minor micro")(3, 10, 0)
        with patch("lidco.doctor.system_checker.sys") as mock_sys:
            mock_sys.version_info = vi
            result = SystemChecker().check_python()
        self.assertEqual(result.status, CheckStatus.PASS)
        self.assertIn("3.10.0", result.message)

    def test_pass_313(self):
        vi = namedtuple("vi", "major minor micro")(3, 13, 1)
        with patch("lidco.doctor.system_checker.sys") as mock_sys:
            mock_sys.version_info = vi
            result = SystemChecker().check_python()
        self.assertEqual(result.status, CheckStatus.PASS)

    def test_fail_39(self):
        vi = namedtuple("vi", "major minor micro")(3, 9, 7)
        with patch("lidco.doctor.system_checker.sys") as mock_sys:
            mock_sys.version_info = vi
            result = SystemChecker().check_python()
        self.assertEqual(result.status, CheckStatus.FAIL)
        self.assertIn("3.9.7", result.message)


class TestCheckGit(unittest.TestCase):
    def test_git_found(self):
        with patch("lidco.doctor.system_checker.shutil.which", return_value="/usr/bin/git"):
            result = SystemChecker().check_git()
        self.assertEqual(result.status, CheckStatus.PASS)

    def test_git_missing(self):
        with patch("lidco.doctor.system_checker.shutil.which", return_value=None):
            result = SystemChecker().check_git()
        self.assertEqual(result.status, CheckStatus.FAIL)
        self.assertIn("not found", result.message)


class TestCheckGhCli(unittest.TestCase):
    def test_gh_found(self):
        with patch("lidco.doctor.system_checker.shutil.which", return_value="/usr/bin/gh"):
            result = SystemChecker().check_gh_cli()
        self.assertEqual(result.status, CheckStatus.PASS)

    def test_gh_missing(self):
        with patch("lidco.doctor.system_checker.shutil.which", return_value=None):
            result = SystemChecker().check_gh_cli()
        self.assertEqual(result.status, CheckStatus.FAIL)


class TestCheckOs(unittest.TestCase):
    @patch("lidco.doctor.system_checker.os.path.exists", return_value=False)
    @patch("lidco.doctor.system_checker.platform.system", return_value="Linux")
    def test_plain_linux(self, _plat, _exists):
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = SystemChecker().check_os()
        self.assertEqual(result.status, CheckStatus.PASS)
        self.assertIn("Linux", result.message)

    @patch("lidco.doctor.system_checker.os.path.exists", return_value=True)
    @patch("lidco.doctor.system_checker.platform.system", return_value="Linux")
    def test_docker_detected(self, _plat, _exists):
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = SystemChecker().check_os()
        self.assertIn("Docker", result.message)


class TestCheckDiskSpace(unittest.TestCase):
    def test_plenty(self):
        _Usage = namedtuple("_Usage", "total used free")
        with patch("lidco.doctor.system_checker.shutil.disk_usage", return_value=_Usage(100e9, 50e9, 50e9)):
            result = SystemChecker().check_disk_space(".")
        self.assertEqual(result.status, CheckStatus.PASS)

    def test_low(self):
        _Usage = namedtuple("_Usage", "total used free")
        with patch("lidco.doctor.system_checker.shutil.disk_usage", return_value=_Usage(100e9, 99.5e9, 0.5e9)):
            result = SystemChecker().check_disk_space(".")
        self.assertEqual(result.status, CheckStatus.WARN)

    def test_os_error(self):
        with patch("lidco.doctor.system_checker.shutil.disk_usage", side_effect=OSError("no")):
            result = SystemChecker().check_disk_space("/bad")
        self.assertEqual(result.status, CheckStatus.SKIP)


class TestRunAllAndSummary(unittest.TestCase):
    def test_run_all_returns_list(self):
        results = [
            CheckResult("a", CheckStatus.PASS, "ok"),
            CheckResult("b", CheckStatus.FAIL, "bad"),
        ]
        checker = SystemChecker()
        summary = checker.summary(results)
        self.assertIn("[PASS]", summary)
        self.assertIn("[FAIL]", summary)
        self.assertIn("ok", summary)
        self.assertIn("bad", summary)
