"""Tests for SystemInfo — Task 850."""

from __future__ import annotations

import sys
import unittest

from lidco.diagnostics.system_info import SystemInfo, SystemReport


class TestSystemReport(unittest.TestCase):
    def test_dataclass_fields(self):
        r = SystemReport("3.13", "Linux", "64bit", "/home", 1234, 8, "utf-8", "UTC")
        self.assertEqual(r.python_version, "3.13")
        self.assertEqual(r.platform, "Linux")
        self.assertEqual(r.architecture, "64bit")
        self.assertEqual(r.cwd, "/home")
        self.assertEqual(r.pid, 1234)
        self.assertEqual(r.cpu_count, 8)
        self.assertEqual(r.encoding, "utf-8")
        self.assertEqual(r.timezone, "UTC")

    def test_cpu_count_none(self):
        r = SystemReport("3.13", "Linux", "64bit", "/", 1, None, "utf-8", "UTC")
        self.assertIsNone(r.cpu_count)


class TestSystemInfoCollect(unittest.TestCase):
    def test_collect_returns_report(self):
        info = SystemInfo(
            _platform_fn=lambda: "TestOS",
            _architecture_fn=lambda: ("64bit", "ELF"),
            _cwd_fn=lambda: "/test",
            _pid_fn=lambda: 42,
            _cpu_count_fn=lambda: 4,
            _encoding_fn=lambda: "utf-8",
            _timezone_fn=lambda: "EST",
            _python_version_fn=lambda: "3.13.0",
        )
        report = info.collect()
        self.assertEqual(report.platform, "TestOS")
        self.assertEqual(report.architecture, "64bit")
        self.assertEqual(report.cwd, "/test")
        self.assertEqual(report.pid, 42)
        self.assertEqual(report.cpu_count, 4)
        self.assertEqual(report.encoding, "utf-8")
        self.assertEqual(report.timezone, "EST")
        self.assertEqual(report.python_version, "3.13.0")

    def test_collect_defaults(self):
        info = SystemInfo()
        report = info.collect()
        self.assertIsInstance(report, SystemReport)
        self.assertIsInstance(report.pid, int)
        self.assertIn(".", report.python_version)

    def test_collect_cpu_count_none(self):
        info = SystemInfo(_cpu_count_fn=lambda: None)
        report = info.collect()
        self.assertIsNone(report.cpu_count)


class TestFormatReport(unittest.TestCase):
    def test_format_contains_sections(self):
        r = SystemReport("3.13", "TestOS", "64bit", "/cwd", 99, 8, "utf-8", "UTC")
        text = SystemInfo.format_report(r)
        self.assertIn("Python", text)
        self.assertIn("Platform", text)
        self.assertIn("TestOS", text)
        self.assertIn("64bit", text)
        self.assertIn("99", text)

    def test_format_contains_all_fields(self):
        r = SystemReport("3.13", "OS", "arm64", "/x", 1, 2, "ascii", "PST")
        text = SystemInfo.format_report(r)
        for field in ["3.13", "OS", "arm64", "/x", "1", "2", "ascii", "PST"]:
            self.assertIn(field, text)


class TestAsDict(unittest.TestCase):
    def test_as_dict_keys(self):
        r = SystemReport("3.13", "OS", "64bit", "/", 1, 4, "utf-8", "UTC")
        d = SystemInfo.as_dict(r)
        expected_keys = {"python_version", "platform", "architecture", "cwd", "pid", "cpu_count", "encoding", "timezone"}
        self.assertEqual(set(d.keys()), expected_keys)

    def test_as_dict_values(self):
        r = SystemReport("3.13", "OS", "64bit", "/tmp", 42, 8, "utf-8", "UTC")
        d = SystemInfo.as_dict(r)
        self.assertEqual(d["pid"], 42)
        self.assertEqual(d["cpu_count"], 8)

    def test_as_dict_returns_dict(self):
        r = SystemReport("3.13", "OS", "64bit", "/", 1, None, "utf-8", "UTC")
        self.assertIsInstance(SystemInfo.as_dict(r), dict)

    def test_as_dict_none_cpu(self):
        r = SystemReport("3.13", "OS", "64bit", "/", 1, None, "utf-8", "UTC")
        d = SystemInfo.as_dict(r)
        self.assertIsNone(d["cpu_count"])


class TestCheckCompatibility(unittest.TestCase):
    def test_no_warnings_modern_python(self):
        info = SystemInfo(_cpu_count_fn=lambda: 4)
        warnings = info.check_compatibility()
        if sys.version_info >= (3, 10):
            self.assertEqual(len([w for w in warnings if "Python" in w]), 0)

    def test_single_cpu_warning(self):
        info = SystemInfo(_cpu_count_fn=lambda: 1)
        warnings = info.check_compatibility()
        self.assertTrue(any("Single CPU" in w for w in warnings))

    def test_multi_cpu_no_warning(self):
        info = SystemInfo(_cpu_count_fn=lambda: 8)
        warnings = info.check_compatibility()
        self.assertFalse(any("CPU" in w for w in warnings))

    def test_returns_list(self):
        info = SystemInfo()
        self.assertIsInstance(info.check_compatibility(), list)


if __name__ == "__main__":
    unittest.main()
