"""Tests for src/lidco/doctor/env_reporter.py."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from lidco.doctor.env_reporter import EnvReport, EnvReporter, EnvSection


class TestCollectPythonInfo(unittest.TestCase):
    def test_has_version(self):
        section = EnvReporter().collect_python_info()
        self.assertEqual(section.title, "Python")
        keys = [k for k, _ in section.items]
        self.assertIn("version", keys)
        self.assertIn("executable", keys)

    def test_venv_none(self):
        with patch.dict("os.environ", {}, clear=True):
            section = EnvReporter().collect_python_info()
        vals = dict(section.items)
        self.assertEqual(vals["virtualenv"], "(none)")


class TestCollectOsInfo(unittest.TestCase):
    @patch("lidco.doctor.env_reporter.platform.platform", return_value="Linux-5.15")
    @patch("lidco.doctor.env_reporter.platform.node", return_value="myhost")
    @patch("lidco.doctor.env_reporter.platform.machine", return_value="x86_64")
    def test_os_section(self, *_mocks):
        import os as _os
        fake_path = "/usr/bin" + _os.pathsep + "/bin"
        with patch.dict("os.environ", {"PATH": fake_path}, clear=True):
            section = EnvReporter().collect_os_info()
        vals = dict(section.items)
        self.assertEqual(vals["platform"], "Linux-5.15")
        self.assertEqual(vals["PATH entries"], "2")


class TestCollectConfigFiles(unittest.TestCase):
    @patch("lidco.doctor.env_reporter.os.path.exists", return_value=True)
    def test_all_found(self, _):
        section = EnvReporter().collect_config_files()
        vals = dict(section.items)
        self.assertTrue(all(v == "found" for v in vals.values()))

    @patch("lidco.doctor.env_reporter.os.path.exists", return_value=False)
    def test_all_missing(self, _):
        section = EnvReporter().collect_config_files()
        vals = dict(section.items)
        self.assertTrue(all(v == "missing" for v in vals.values()))


class TestCollectEnvVars(unittest.TestCase):
    def test_masks_values(self):
        env = {"ANTHROPIC_API_KEY": "sk-ant-secret123", "HOME": "/home/user"}
        with patch.dict("os.environ", env, clear=True):
            section = EnvReporter().collect_env_vars()
        vals = dict(section.items)
        self.assertIn("ANTHROPIC_API_KEY", vals)
        self.assertNotIn("HOME", vals)
        self.assertTrue(vals["ANTHROPIC_API_KEY"].endswith("..."))

    def test_no_relevant_vars(self):
        with patch.dict("os.environ", {"HOME": "/home"}, clear=True):
            section = EnvReporter().collect_env_vars()
        keys = [k for k, _ in section.items]
        self.assertIn("(none)", keys)


class TestGenerate(unittest.TestCase):
    def test_report_has_sections(self):
        report = EnvReporter().generate()
        self.assertIsInstance(report, EnvReport)
        self.assertEqual(len(report.sections), 4)
        self.assertTrue(len(report.generated_at) > 0)


class TestFormatReport(unittest.TestCase):
    def test_format_contains_titles(self):
        report = EnvReport(
            sections=(
                EnvSection("Alpha", (("k1", "v1"),)),
                EnvSection("Beta", (("k2", "v2"),)),
            ),
            generated_at="2026-04-01T00:00:00Z",
        )
        text = EnvReporter().format_report(report)
        self.assertIn("== Alpha ==", text)
        self.assertIn("== Beta ==", text)
        self.assertIn("k1: v1", text)


class TestSummary(unittest.TestCase):
    def test_summary_returns_string(self):
        s = EnvReporter().summary()
        self.assertIsInstance(s, str)
        self.assertIn("Environment Report", s)
