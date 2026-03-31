"""Tests for StreamMultiplexer."""
from __future__ import annotations

import unittest

from lidco.streaming.multiplexer import StreamMultiplexer, StreamEntry


class TestStreamEntry(unittest.TestCase):
    def test_fields(self):
        e = StreamEntry(content="hi", stream_name="s1", timestamp=1.0, sequence=1)
        self.assertEqual(e.content, "hi")
        self.assertEqual(e.stream_name, "s1")
        self.assertEqual(e.sequence, 1)


class TestStreamMultiplexer(unittest.TestCase):
    def setUp(self):
        self.mux = StreamMultiplexer()

    # --- add / remove stream ---
    def test_add_stream(self):
        self.mux.add_stream("stdout")
        self.assertIn("stdout", self.mux.stream_names)

    def test_add_stream_idempotent(self):
        self.mux.add_stream("a")
        self.mux.add_stream("a")
        self.assertEqual(self.mux.stream_names.count("a"), 1)

    def test_remove_stream(self):
        self.mux.add_stream("a")
        self.mux.remove_stream("a")
        self.assertNotIn("a", self.mux.stream_names)

    def test_remove_nonexistent(self):
        self.mux.remove_stream("nope")  # should not raise

    def test_stream_names_empty(self):
        self.assertEqual(self.mux.stream_names, [])

    # --- write ---
    def test_write_to_stream(self):
        self.mux.add_stream("s1")
        self.mux.write("s1", "hello")
        self.assertEqual(self.mux.total_entries, 1)

    def test_write_unknown_stream_raises(self):
        with self.assertRaises(KeyError):
            self.mux.write("nope", "data")

    def test_write_increments_sequence(self):
        self.mux.add_stream("s")
        self.mux.write("s", "a")
        self.mux.write("s", "b")
        entries = self.mux.read_stream("s")
        self.assertEqual(entries[0].sequence, 1)
        self.assertEqual(entries[1].sequence, 2)

    def test_write_sets_stream_name(self):
        self.mux.add_stream("err")
        self.mux.write("err", "x")
        self.assertEqual(self.mux.read_stream("err")[0].stream_name, "err")

    # --- read_all ---
    def test_read_all_empty(self):
        self.assertEqual(self.mux.read_all(), [])

    def test_read_all_merged(self):
        self.mux.add_stream("a")
        self.mux.add_stream("b")
        self.mux.write("a", "1")
        self.mux.write("b", "2")
        self.mux.write("a", "3")
        result = self.mux.read_all()
        self.assertEqual(len(result), 3)

    def test_read_all_since_sequence(self):
        self.mux.add_stream("s")
        self.mux.write("s", "a")
        self.mux.write("s", "b")
        self.mux.write("s", "c")
        result = self.mux.read_all(since_sequence=2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].content, "c")

    # --- read_stream ---
    def test_read_stream(self):
        self.mux.add_stream("a")
        self.mux.add_stream("b")
        self.mux.write("a", "x")
        self.mux.write("b", "y")
        self.assertEqual(len(self.mux.read_stream("a")), 1)
        self.assertEqual(self.mux.read_stream("a")[0].content, "x")

    def test_read_stream_nonexistent(self):
        self.assertEqual(self.mux.read_stream("nope"), [])

    # --- total_entries ---
    def test_total_entries_empty(self):
        self.assertEqual(self.mux.total_entries, 0)

    def test_total_entries_counts_all(self):
        self.mux.add_stream("a")
        self.mux.add_stream("b")
        self.mux.write("a", "1")
        self.mux.write("b", "2")
        self.assertEqual(self.mux.total_entries, 2)

    # --- entries preserved after remove ---
    def test_entries_preserved_after_remove(self):
        self.mux.add_stream("s")
        self.mux.write("s", "data")
        self.mux.remove_stream("s")
        # read_all still contains the entry
        self.assertEqual(len(self.mux.read_all()), 1)


if __name__ == "__main__":
    unittest.main()
