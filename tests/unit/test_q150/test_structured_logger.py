"""Tests for Q150 StructuredLogger."""
from __future__ import annotations

import json
import unittest

from lidco.logging.structured_logger import LogRecord, StructuredLogger


class TestLogRecord(unittest.TestCase):
    def test_defaults(self):
        r = LogRecord(level="info", message="hi", timestamp=1.0, logger_name="x")
        self.assertEqual(r.context, {})
        self.assertIsNone(r.correlation_id)

    def test_with_context(self):
        r = LogRecord(level="info", message="m", timestamp=0, logger_name="n", context={"k": "v"})
        self.assertEqual(r.context["k"], "v")

    def test_with_correlation_id(self):
        r = LogRecord(level="debug", message="m", timestamp=0, logger_name="n", correlation_id="abc")
        self.assertEqual(r.correlation_id, "abc")


class TestStructuredLogger(unittest.TestCase):
    def setUp(self):
        self.log = StructuredLogger("test")

    def test_debug(self):
        self.log.debug("d")
        self.assertEqual(len(self.log.records), 1)
        self.assertEqual(self.log.records[0].level, "debug")

    def test_info(self):
        self.log.info("i")
        self.assertEqual(self.log.records[0].level, "info")

    def test_warning(self):
        self.log.warning("w")
        self.assertEqual(self.log.records[0].level, "warning")

    def test_error(self):
        self.log.error("e")
        self.assertEqual(self.log.records[0].level, "error")

    def test_critical(self):
        self.log.critical("c")
        self.assertEqual(self.log.records[0].level, "critical")

    def test_message_stored(self):
        self.log.info("hello world")
        self.assertEqual(self.log.records[0].message, "hello world")

    def test_logger_name(self):
        self.log.info("x")
        self.assertEqual(self.log.records[0].logger_name, "test")

    def test_timestamp_set(self):
        self.log.info("x")
        self.assertGreater(self.log.records[0].timestamp, 0)

    def test_extra_context(self):
        self.log.info("x", user="alice")
        self.assertEqual(self.log.records[0].context["user"], "alice")

    def test_min_level_filters(self):
        log = StructuredLogger("t", min_level="warning")
        log.debug("d")
        log.info("i")
        log.warning("w")
        log.error("e")
        self.assertEqual(len(log.records), 2)

    def test_min_level_critical(self):
        log = StructuredLogger("t", min_level="critical")
        log.error("e")
        log.critical("c")
        self.assertEqual(len(log.records), 1)

    def test_clear(self):
        self.log.info("x")
        self.log.clear()
        self.assertEqual(len(self.log.records), 0)

    def test_records_returns_copy(self):
        self.log.info("x")
        recs = self.log.records
        recs.clear()
        self.assertEqual(len(self.log.records), 1)

    def test_with_context_immutable(self):
        child = self.log.with_context(env="prod")
        child.info("child msg")
        self.assertEqual(child.records[0].context["env"], "prod")
        # Parent logger didn't get the context key
        self.log.info("parent msg")
        self.assertNotIn("env", self.log.records[-1].context)

    def test_with_context_merges(self):
        child = self.log.with_context(a=1)
        grandchild = child.with_context(b=2)
        grandchild.info("gc")
        ctx = grandchild.records[-1].context
        self.assertEqual(ctx["a"], 1)
        self.assertEqual(ctx["b"], 2)

    def test_with_context_shares_records(self):
        child = self.log.with_context(x=1)
        child.info("from child")
        self.assertEqual(len(self.log.records), 1)

    def test_with_correlation(self):
        child = self.log.with_correlation("req-123")
        child.info("correlated")
        self.assertEqual(child.records[-1].correlation_id, "req-123")

    def test_with_correlation_shares_records(self):
        child = self.log.with_correlation("c1")
        child.info("x")
        self.assertEqual(len(self.log.records), 1)

    def test_format_json(self):
        self.log.info("hello", key="val")
        rec = self.log.records[0]
        out = StructuredLogger.format_json(rec)
        parsed = json.loads(out)
        self.assertEqual(parsed["level"], "info")
        self.assertEqual(parsed["message"], "hello")
        self.assertEqual(parsed["context"]["key"], "val")

    def test_format_json_no_context(self):
        self.log.info("bare")
        rec = self.log.records[0]
        out = json.loads(StructuredLogger.format_json(rec))
        self.assertNotIn("context", out)

    def test_format_json_correlation(self):
        child = self.log.with_correlation("cid")
        child.info("x")
        out = json.loads(StructuredLogger.format_json(child.records[-1]))
        self.assertEqual(out["correlation_id"], "cid")

    def test_format_text(self):
        self.log.error("boom", code=500)
        rec = self.log.records[0]
        txt = StructuredLogger.format_text(rec)
        self.assertIn("[ERROR]", txt)
        self.assertIn("test:", txt)
        self.assertIn("boom", txt)
        self.assertIn("500", txt)

    def test_format_text_no_context(self):
        self.log.info("plain")
        txt = StructuredLogger.format_text(self.log.records[0])
        self.assertIn("[INFO]", txt)
        self.assertNotIn("{}", txt)


if __name__ == "__main__":
    unittest.main()
