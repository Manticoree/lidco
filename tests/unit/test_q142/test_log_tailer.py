"""Tests for LogTailer."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from lidco.streaming.line_buffer import LineBuffer
from lidco.streaming.log_tailer import LogTailer, TailEntry


class TestTailEntry(unittest.TestCase):
    def test_fields(self):
        e = TailEntry(line="hi", line_number=1, timestamp=1.0, matched=False)
        self.assertEqual(e.line, "hi")
        self.assertEqual(e.line_number, 1)
        self.assertFalse(e.matched)


class TestLogTailer(unittest.TestCase):
    def setUp(self):
        self.tailer = LogTailer()

    # --- tail ---
    def test_tail_empty(self):
        self.assertEqual(self.tailer.tail(), [])

    def test_tail_returns_entries(self):
        self.tailer.add_line("a")
        self.tailer.add_line("b")
        result = self.tailer.tail(10)
        self.assertEqual(len(result), 2)

    def test_tail_limits(self):
        for i in range(20):
            self.tailer.add_line(f"line {i}")
        result = self.tailer.tail(5)
        self.assertEqual(len(result), 5)

    def test_tail_returns_tail_entries(self):
        self.tailer.add_line("x")
        result = self.tailer.tail(1)
        self.assertIsInstance(result[0], TailEntry)

    def test_tail_default_n(self):
        for i in range(15):
            self.tailer.add_line(f"line {i}")
        result = self.tailer.tail()
        self.assertEqual(len(result), 10)

    # --- add_line ---
    def test_add_line_increases_count(self):
        self.tailer.add_line("a")
        self.tailer.add_line("b")
        self.assertEqual(len(self.tailer.tail(100)), 2)

    def test_add_line_notifies_followers(self):
        cb = MagicMock()
        self.tailer.follow(cb)
        self.tailer.add_line("test")
        cb.assert_called_once()
        entry = cb.call_args[0][0]
        self.assertIsInstance(entry, TailEntry)
        self.assertEqual(entry.line, "test")

    def test_add_line_notifies_multiple_followers(self):
        cb1 = MagicMock()
        cb2 = MagicMock()
        self.tailer.follow(cb1)
        self.tailer.follow(cb2)
        self.tailer.add_line("x")
        cb1.assert_called_once()
        cb2.assert_called_once()

    # --- follow / unfollow ---
    def test_follow_count(self):
        self.assertEqual(self.tailer.follower_count, 0)
        cb = MagicMock()
        self.tailer.follow(cb)
        self.assertEqual(self.tailer.follower_count, 1)

    def test_follow_idempotent(self):
        cb = MagicMock()
        self.tailer.follow(cb)
        self.tailer.follow(cb)
        self.assertEqual(self.tailer.follower_count, 1)

    def test_unfollow(self):
        cb = MagicMock()
        self.tailer.follow(cb)
        self.tailer.unfollow(cb)
        self.assertEqual(self.tailer.follower_count, 0)

    def test_unfollow_nonexistent(self):
        cb = MagicMock()
        self.tailer.unfollow(cb)  # should not raise
        self.assertEqual(self.tailer.follower_count, 0)

    def test_unfollow_stops_notifications(self):
        cb = MagicMock()
        self.tailer.follow(cb)
        self.tailer.unfollow(cb)
        self.tailer.add_line("x")
        cb.assert_not_called()

    # --- grep ---
    def test_grep_finds_matches(self):
        self.tailer.add_line("error: boom")
        self.tailer.add_line("info: ok")
        result = self.tailer.grep("error")
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].matched)

    def test_grep_no_matches(self):
        self.tailer.add_line("hello")
        result = self.tailer.grep("xyz")
        self.assertEqual(len(result), 0)

    def test_grep_last_n(self):
        for i in range(10):
            self.tailer.add_line(f"line {i}")
        result = self.tailer.grep(r"line \d", last_n=3)
        self.assertEqual(len(result), 3)

    def test_grep_regex(self):
        self.tailer.add_line("code 200")
        self.tailer.add_line("code 404")
        result = self.tailer.grep(r"code 4\d{2}")
        self.assertEqual(len(result), 1)

    # --- with shared buffer ---
    def test_shared_buffer(self):
        buf = LineBuffer()
        buf.write("pre-existing")
        tailer = LogTailer(buffer=buf)
        result = tailer.tail(10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].line, "pre-existing")


if __name__ == "__main__":
    unittest.main()
