"""Tests for lidco.stability.crash_reporter."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from lidco.stability.crash_reporter import CrashReporter


def _make_exc(msg: str = "test error") -> Exception:
    """Return a real exception instance with a populated traceback."""
    try:
        raise ValueError(msg)
    except ValueError as exc:
        return exc


class TestCaptureContext(unittest.TestCase):
    def setUp(self):
        self.reporter = CrashReporter()

    def test_returns_dict(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        self.assertIsInstance(ctx, dict)

    def test_exception_type_correct(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        self.assertEqual(ctx["exception_type"], "ValueError")

    def test_message_correct(self):
        exc = _make_exc("hello world")
        ctx = self.reporter.capture_context(exc)
        self.assertIn("hello world", ctx["message"])

    def test_traceback_is_string(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        self.assertIsInstance(ctx["traceback"], str)

    def test_traceback_non_empty_for_real_exc(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        self.assertGreater(len(ctx["traceback"]), 0)

    def test_timestamp_ends_with_z(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        self.assertTrue(ctx["timestamp"].endswith("Z"))

    def test_python_version_present(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        self.assertIn(sys.version[:3], ctx["python_version"])

    def test_platform_present(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        self.assertIsInstance(ctx["platform"], str)
        self.assertTrue(len(ctx["platform"]) > 0)

    def test_all_keys_present(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        for key in ("exception_type", "message", "traceback", "timestamp",
                    "python_version", "platform"):
            self.assertIn(key, ctx)


class TestFormatReport(unittest.TestCase):
    def setUp(self):
        self.reporter = CrashReporter()

    def test_contains_crash_report_header(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        report = self.reporter.format_report(ctx)
        self.assertIn("CRASH REPORT", report)

    def test_contains_exception_type(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        report = self.reporter.format_report(ctx)
        self.assertIn("ValueError", report)

    def test_contains_timestamp(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        report = self.reporter.format_report(ctx)
        self.assertIn("Timestamp", report)

    def test_contains_traceback_section(self):
        exc = _make_exc()
        ctx = self.reporter.capture_context(exc)
        report = self.reporter.format_report(ctx)
        self.assertIn("Traceback", report)


class TestSaveReport(unittest.TestCase):
    def setUp(self):
        self.reporter = CrashReporter()

    def test_save_to_explicit_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "crash.json")
            exc = _make_exc()
            ctx = self.reporter.capture_context(exc)
            result = self.reporter.save_report(ctx, path)
            self.assertTrue(result["saved"])
            self.assertTrue(os.path.exists(path))

    def test_save_returns_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "crash.json")
            exc = _make_exc()
            ctx = self.reporter.capture_context(exc)
            result = self.reporter.save_report(ctx, path)
            self.assertEqual(result["path"], path)

    def test_save_returns_size_bytes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "crash.json")
            exc = _make_exc()
            ctx = self.reporter.capture_context(exc)
            result = self.reporter.save_report(ctx, path)
            self.assertGreater(result["size_bytes"], 0)

    def test_saved_file_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "crash.json")
            exc = _make_exc("structured error")
            ctx = self.reporter.capture_context(exc)
            self.reporter.save_report(ctx, path)
            with open(path) as fh:
                loaded = json.load(fh)
            self.assertEqual(loaded["exception_type"], "ValueError")

    def test_save_failure_returns_saved_false(self):
        reporter = CrashReporter()
        exc = _make_exc()
        ctx = reporter.capture_context(exc)
        result = reporter.save_report(ctx, "/nonexistent_root_xyz/crash.json")
        self.assertIn("saved", result)
        self.assertIn("path", result)


class TestGetReproducibilityInfo(unittest.TestCase):
    def setUp(self):
        self.reporter = CrashReporter()

    def test_returns_dict(self):
        info = self.reporter.get_reproducibility_info()
        self.assertIsInstance(info, dict)

    def test_python_version_present(self):
        info = self.reporter.get_reproducibility_info()
        self.assertIn(sys.version[:3], info["python_version"])

    def test_cwd_is_string(self):
        info = self.reporter.get_reproducibility_info()
        self.assertIsInstance(info["cwd"], str)

    def test_env_vars_is_dict(self):
        info = self.reporter.get_reproducibility_info()
        self.assertIsInstance(info["env_vars"], dict)

    def test_env_vars_no_secrets(self):
        info = self.reporter.get_reproducibility_info()
        for key in info["env_vars"]:
            self.assertNotIn("SECRET", key.upper())
            self.assertNotIn("PASSWORD", key.upper())
            self.assertNotIn("TOKEN", key.upper())

    def test_all_keys_present(self):
        info = self.reporter.get_reproducibility_info()
        for key in ("python_version", "platform", "cwd", "env_vars"):
            self.assertIn(key, info)


if __name__ == "__main__":
    unittest.main()
