"""Tests for Q133 ExecutionLog."""
from __future__ import annotations
import time
import unittest
from lidco.debug.execution_log import ExecutionLog, LogEntry


class TestLogEntry(unittest.TestCase):
    def test_defaults(self):
        entry = LogEntry(id="1", level="info", message="hello")
        self.assertEqual(entry.source, "")
        self.assertEqual(entry.timestamp, 0.0)
        self.assertEqual(entry.data, {})


class TestExecutionLog(unittest.TestCase):
    def setUp(self):
        self.log = ExecutionLog()

    def test_log_returns_entry(self):
        entry = self.log.log("info", "test message")
        self.assertIsInstance(entry, LogEntry)

    def test_log_level_stored(self):
        self.log.log("warning", "beware")
        entries = self.log.filter(level="warning")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].level, "warning")

    def test_log_message_stored(self):
        self.log.log("info", "hello world")
        entries = self.log.tail(1)
        self.assertEqual(entries[0].message, "hello world")

    def test_debug_helper(self):
        entry = self.log.debug("debug msg")
        self.assertEqual(entry.level, "debug")

    def test_info_helper(self):
        entry = self.log.info("info msg")
        self.assertEqual(entry.level, "info")

    def test_warning_helper(self):
        entry = self.log.warning("warn msg")
        self.assertEqual(entry.level, "warning")

    def test_error_helper(self):
        entry = self.log.error("err msg")
        self.assertEqual(entry.level, "error")

    def test_source_stored(self):
        self.log.log("info", "msg", source="my_module")
        entries = self.log.filter(source="my_module")
        self.assertEqual(len(entries), 1)

    def test_data_stored(self):
        entry = self.log.log("info", "msg", data={"key": "val"})
        self.assertEqual(entry.data["key"], "val")

    def test_timestamp_set(self):
        before = time.time()
        entry = self.log.info("msg")
        self.assertGreaterEqual(entry.timestamp, before)

    def test_unique_ids(self):
        e1 = self.log.info("a")
        e2 = self.log.info("b")
        self.assertNotEqual(e1.id, e2.id)

    def test_filter_by_level(self):
        self.log.info("info1")
        self.log.error("err1")
        self.log.info("info2")
        infos = self.log.filter(level="info")
        self.assertEqual(len(infos), 2)

    def test_filter_by_source(self):
        self.log.log("info", "a", source="mod_a")
        self.log.log("info", "b", source="mod_b")
        filtered = self.log.filter(source="mod_a")
        self.assertEqual(len(filtered), 1)

    def test_filter_by_since(self):
        self.log.info("old")
        marker = time.time()
        self.log.info("new")
        recent = self.log.filter(since=marker)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].message, "new")

    def test_filter_combined(self):
        self.log.log("info", "a", source="s1")
        self.log.log("error", "b", source="s1")
        self.log.log("info", "c", source="s2")
        filtered = self.log.filter(level="info", source="s1")
        self.assertEqual(len(filtered), 1)

    def test_tail_default(self):
        for i in range(25):
            self.log.info(f"msg {i}")
        tail = self.log.tail()
        self.assertEqual(len(tail), 20)

    def test_tail_n(self):
        for i in range(10):
            self.log.info(f"msg {i}")
        tail = self.log.tail(5)
        self.assertEqual(len(tail), 5)
        self.assertEqual(tail[-1].message, "msg 9")

    def test_max_entries_enforced(self):
        log = ExecutionLog(max_entries=5)
        for i in range(10):
            log.info(f"msg {i}")
        self.assertEqual(len(log), 5)

    def test_clear(self):
        self.log.info("x")
        self.log.clear()
        self.assertEqual(len(self.log), 0)

    def test_len(self):
        self.assertEqual(len(self.log), 0)
        self.log.info("a")
        self.log.info("b")
        self.assertEqual(len(self.log), 2)

    def test_filter_no_criteria(self):
        self.log.info("a")
        self.log.error("b")
        all_entries = self.log.filter()
        self.assertEqual(len(all_entries), 2)

    def test_data_defaults_empty(self):
        entry = self.log.info("msg")
        self.assertEqual(entry.data, {})

    def test_level_case_insensitive(self):
        entry = self.log.log("INFO", "msg")
        self.assertEqual(entry.level, "info")


if __name__ == "__main__":
    unittest.main()
