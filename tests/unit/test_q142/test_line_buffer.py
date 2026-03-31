"""Tests for LineBuffer."""
from __future__ import annotations

import time
import unittest

from lidco.streaming.line_buffer import LineBuffer, BufferedLine


class TestBufferedLine(unittest.TestCase):
    def test_dataclass_fields(self):
        bl = BufferedLine(text="hello", timestamp=1.0, line_number=1)
        self.assertEqual(bl.text, "hello")
        self.assertEqual(bl.timestamp, 1.0)
        self.assertEqual(bl.line_number, 1)
        self.assertEqual(bl.source, "default")

    def test_custom_source(self):
        bl = BufferedLine(text="x", timestamp=0, line_number=0, source="stderr")
        self.assertEqual(bl.source, "stderr")


class TestLineBuffer(unittest.TestCase):
    def setUp(self):
        self.buf = LineBuffer(max_lines=100)

    # --- write ---
    def test_write_single_line(self):
        self.buf.write("hello")
        self.assertEqual(self.buf.line_count, 1)

    def test_write_multiline(self):
        self.buf.write("a\nb\nc")
        self.assertEqual(self.buf.line_count, 3)

    def test_write_source(self):
        self.buf.write("x", source="stderr")
        lines = self.buf.read_lines()
        self.assertEqual(lines[0].source, "stderr")

    def test_write_timestamp(self):
        before = time.time()
        self.buf.write("x")
        after = time.time()
        bl = self.buf.read_lines()[0]
        self.assertGreaterEqual(bl.timestamp, before)
        self.assertLessEqual(bl.timestamp, after)

    def test_write_increments_line_number(self):
        self.buf.write("a")
        self.buf.write("b")
        lines = self.buf.read_lines()
        self.assertEqual(lines[0].line_number, 1)
        self.assertEqual(lines[1].line_number, 2)

    # --- max_lines ---
    def test_max_lines_trims(self):
        buf = LineBuffer(max_lines=3)
        for i in range(5):
            buf.write(str(i))
        self.assertEqual(buf.line_count, 3)
        texts = [bl.text for bl in buf.read_lines()]
        self.assertEqual(texts, ["2", "3", "4"])

    # --- read_lines ---
    def test_read_lines_all(self):
        self.buf.write("a\nb\nc")
        self.assertEqual(len(self.buf.read_lines()), 3)

    def test_read_lines_n(self):
        self.buf.write("a\nb\nc\nd")
        result = self.buf.read_lines(2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].text, "c")
        self.assertEqual(result[1].text, "d")

    def test_read_lines_n_larger_than_count(self):
        self.buf.write("a")
        result = self.buf.read_lines(10)
        self.assertEqual(len(result), 1)

    # --- read_new ---
    def test_read_new_returns_all_first_call(self):
        self.buf.write("a\nb")
        new = self.buf.read_new()
        self.assertEqual(len(new), 2)

    def test_read_new_returns_only_new(self):
        self.buf.write("a")
        self.buf.read_new()
        self.buf.write("b")
        new = self.buf.read_new()
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].text, "b")

    def test_read_new_returns_empty_when_no_new(self):
        self.buf.write("a")
        self.buf.read_new()
        new = self.buf.read_new()
        self.assertEqual(len(new), 0)

    # --- flush ---
    def test_flush_returns_all(self):
        self.buf.write("a\nb")
        flushed = self.buf.flush()
        self.assertEqual(len(flushed), 2)

    def test_flush_clears_buffer(self):
        self.buf.write("a")
        self.buf.flush()
        self.assertTrue(self.buf.is_empty)

    # --- is_empty / line_count ---
    def test_is_empty_initially(self):
        self.assertTrue(self.buf.is_empty)

    def test_not_empty_after_write(self):
        self.buf.write("x")
        self.assertFalse(self.buf.is_empty)

    # --- search ---
    def test_search_finds_match(self):
        self.buf.write("error: something failed")
        self.buf.write("info: all good")
        matches = self.buf.search("error")
        self.assertEqual(len(matches), 1)
        self.assertIn("error", matches[0].text)

    def test_search_regex(self):
        self.buf.write("line 1")
        self.buf.write("line 22")
        matches = self.buf.search(r"line \d{2}")
        self.assertEqual(len(matches), 1)

    def test_search_no_match(self):
        self.buf.write("hello")
        matches = self.buf.search("xyz")
        self.assertEqual(len(matches), 0)

    # --- clear ---
    def test_clear(self):
        self.buf.write("a\nb")
        self.buf.clear()
        self.assertTrue(self.buf.is_empty)
        self.assertEqual(self.buf.line_count, 0)


if __name__ == "__main__":
    unittest.main()
