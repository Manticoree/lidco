"""Tests for lidco.streaming.stream_buffer — StreamBuffer."""
from __future__ import annotations

import unittest

from lidco.streaming.stream_buffer import (
    BufferOverflowError,
    OverflowPolicy,
    StreamBuffer,
)


class TestStreamBufferInit(unittest.TestCase):
    def test_defaults(self):
        buf = StreamBuffer()
        self.assertEqual(buf.size, 0)
        self.assertTrue(buf.is_empty)
        self.assertFalse(buf.is_full)

    def test_invalid_capacity(self):
        with self.assertRaises(ValueError):
            StreamBuffer(capacity=0)

    def test_string_overflow_policy(self):
        buf = StreamBuffer(overflow_policy="drop_oldest")
        self.assertEqual(buf.stats()["overflow_policy"], "drop_oldest")


class TestWriteRead(unittest.TestCase):
    def setUp(self):
        self.buf = StreamBuffer(capacity=5)

    def test_write_and_read(self):
        self.buf.write("a")
        self.buf.write("b")
        self.assertEqual(self.buf.read(2), ["a", "b"])

    def test_read_empty(self):
        self.assertEqual(self.buf.read(), [])

    def test_write_full_drain(self):
        for c in "abcde":
            self.buf.write(c)
        self.assertTrue(self.buf.is_full)
        result = self.buf.drain()
        self.assertEqual(result, ["a", "b", "c", "d", "e"])
        self.assertTrue(self.buf.is_empty)

    def test_peek_does_not_consume(self):
        self.buf.write("x")
        self.assertEqual(self.buf.peek(), ["x"])
        self.assertEqual(self.buf.size, 1)

    def test_peek_multiple(self):
        for c in "abc":
            self.buf.write(c)
        self.assertEqual(self.buf.peek(2), ["a", "b"])
        self.assertEqual(self.buf.size, 3)


class TestOverflowDropOldest(unittest.TestCase):
    def test_drop_oldest(self):
        buf = StreamBuffer(capacity=3, overflow_policy=OverflowPolicy.DROP_OLDEST)
        for c in "abcd":
            buf.write(c)
        self.assertEqual(buf.size, 3)
        self.assertEqual(buf.drain(), ["b", "c", "d"])
        self.assertEqual(buf.stats()["overflow_count"], 1)


class TestOverflowBlock(unittest.TestCase):
    def test_block_returns_false(self):
        buf = StreamBuffer(capacity=2, overflow_policy=OverflowPolicy.BLOCK)
        buf.write("a")
        buf.write("b")
        self.assertFalse(buf.write("c"))
        self.assertEqual(buf.size, 2)


class TestOverflowError(unittest.TestCase):
    def test_error_raises(self):
        buf = StreamBuffer(capacity=2, overflow_policy=OverflowPolicy.ERROR)
        buf.write("a")
        buf.write("b")
        with self.assertRaises(BufferOverflowError):
            buf.write("c")


class TestRingBufferWrapAround(unittest.TestCase):
    def test_wrap_around(self):
        buf = StreamBuffer(capacity=3)
        buf.write("a")
        buf.write("b")
        buf.write("c")
        buf.read(2)
        buf.write("d")
        buf.write("e")
        self.assertEqual(buf.drain(), ["c", "d", "e"])


class TestStats(unittest.TestCase):
    def test_stats_keys(self):
        s = StreamBuffer().stats()
        for key in ("capacity", "used", "overflow_count", "total_written", "total_read"):
            self.assertIn(key, s)

    def test_stats_counts(self):
        buf = StreamBuffer(capacity=5)
        buf.write("a")
        buf.write("b")
        buf.read(1)
        s = buf.stats()
        self.assertEqual(s["total_written"], 2)
        self.assertEqual(s["total_read"], 1)
        self.assertEqual(s["used"], 1)


if __name__ == "__main__":
    unittest.main()
