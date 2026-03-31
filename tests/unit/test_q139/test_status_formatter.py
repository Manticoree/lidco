"""Tests for Q139 StatusFormatter."""
from __future__ import annotations

import unittest

from lidco.ui.status_formatter import StatusFormatter, StatusEntry


class TestStatusEntry(unittest.TestCase):
    def test_fields(self):
        se = StatusEntry(label="x", status="ok", detail="d", timestamp=1.0)
        self.assertEqual(se.label, "x")
        self.assertEqual(se.status, "ok")
        self.assertEqual(se.detail, "d")
        self.assertEqual(se.timestamp, 1.0)


class TestStatusFormatterSuccess(unittest.TestCase):
    def test_success_basic(self):
        sf = StatusFormatter()
        result = sf.success("Build")
        self.assertIn("v", result)
        self.assertIn("Build", result)

    def test_success_with_detail(self):
        sf = StatusFormatter()
        result = sf.success("Build", "completed")
        self.assertIn("completed", result)
        self.assertIn("--", result)


class TestStatusFormatterError(unittest.TestCase):
    def test_error_basic(self):
        sf = StatusFormatter()
        result = sf.error("Tests")
        self.assertIn("x", result)
        self.assertIn("Tests", result)

    def test_error_with_detail(self):
        sf = StatusFormatter()
        result = sf.error("Tests", "2 failures")
        self.assertIn("2 failures", result)


class TestStatusFormatterWarning(unittest.TestCase):
    def test_warning_basic(self):
        sf = StatusFormatter()
        result = sf.warning("Lint")
        self.assertIn("!", result)
        self.assertIn("Lint", result)

    def test_warning_with_detail(self):
        sf = StatusFormatter()
        result = sf.warning("Lint", "3 warnings")
        self.assertIn("3 warnings", result)


class TestStatusFormatterInfo(unittest.TestCase):
    def test_info_basic(self):
        sf = StatusFormatter()
        result = sf.info("Coverage")
        self.assertIn(">", result)
        self.assertIn("Coverage", result)

    def test_info_with_detail(self):
        sf = StatusFormatter()
        result = sf.info("Coverage", "87%")
        self.assertIn("87%", result)


class TestSpinnerFrame(unittest.TestCase):
    def test_spinner_first_frame(self):
        sf = StatusFormatter()
        result = sf.spinner_frame("Loading", 0)
        self.assertIn("Loading", result)
        self.assertTrue(len(result) > len("Loading"))

    def test_spinner_wraps_around(self):
        sf = StatusFormatter()
        r0 = sf.spinner_frame("X", 0)
        r10 = sf.spinner_frame("X", 10)
        # frame 10 % 10 == 0, same char
        self.assertEqual(r0, r10)

    def test_spinner_different_frames(self):
        sf = StatusFormatter()
        r0 = sf.spinner_frame("X", 0)
        r1 = sf.spinner_frame("X", 1)
        self.assertNotEqual(r0, r1)


class TestFormatDuration(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(StatusFormatter.format_duration(1.2), "1.2s")

    def test_minutes(self):
        result = StatusFormatter.format_duration(225)
        self.assertIn("3m", result)
        self.assertIn("45s", result)

    def test_hours(self):
        result = StatusFormatter.format_duration(4980)
        self.assertIn("1h", result)
        self.assertIn("23m", result)

    def test_zero(self):
        self.assertEqual(StatusFormatter.format_duration(0), "0.0s")

    def test_negative_clamps(self):
        self.assertEqual(StatusFormatter.format_duration(-5), "0.0s")


class TestFormatBytes(unittest.TestCase):
    def test_bytes(self):
        self.assertEqual(StatusFormatter.format_bytes(500), "500 B")

    def test_kilobytes(self):
        result = StatusFormatter.format_bytes(1536)
        self.assertIn("KB", result)

    def test_megabytes(self):
        result = StatusFormatter.format_bytes(24_000_000)
        self.assertIn("MB", result)

    def test_gigabytes(self):
        result = StatusFormatter.format_bytes(2_000_000_000)
        self.assertIn("GB", result)

    def test_zero(self):
        self.assertEqual(StatusFormatter.format_bytes(0), "0 B")

    def test_negative_clamps(self):
        self.assertEqual(StatusFormatter.format_bytes(-10), "0 B")


class TestHistory(unittest.TestCase):
    def test_empty_history(self):
        sf = StatusFormatter()
        self.assertEqual(sf.history, [])

    def test_history_records_all(self):
        sf = StatusFormatter()
        sf.success("A")
        sf.error("B")
        sf.warning("C")
        sf.info("D")
        self.assertEqual(len(sf.history), 4)

    def test_history_entry_types(self):
        sf = StatusFormatter()
        sf.success("X", "detail")
        entry = sf.history[0]
        self.assertIsInstance(entry, StatusEntry)
        self.assertEqual(entry.status, "success")
        self.assertEqual(entry.label, "X")
        self.assertEqual(entry.detail, "detail")


if __name__ == "__main__":
    unittest.main()
