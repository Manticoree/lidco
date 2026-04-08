"""Tests for lidco.logintel.parser — Log Parser."""

from __future__ import annotations

import json
import unittest

from lidco.logintel.parser import LogEntry, LogFormat, LogParser, ParseResult


class TestLogFormat(unittest.TestCase):
    """Tests for LogFormat enum."""

    def test_values(self) -> None:
        self.assertEqual(LogFormat.JSON.value, "json")
        self.assertEqual(LogFormat.SYSLOG.value, "syslog")
        self.assertEqual(LogFormat.CUSTOM.value, "custom")
        self.assertEqual(LogFormat.UNKNOWN.value, "unknown")


class TestLogEntry(unittest.TestCase):
    """Tests for LogEntry dataclass."""

    def test_create_entry(self) -> None:
        entry = LogEntry(timestamp="2026-01-01T00:00:00", level="INFO", message="hello")
        self.assertEqual(entry.timestamp, "2026-01-01T00:00:00")
        self.assertEqual(entry.level, "INFO")
        self.assertEqual(entry.message, "hello")
        self.assertEqual(entry.source, "")
        self.assertEqual(entry.fields, {})

    def test_frozen(self) -> None:
        entry = LogEntry(timestamp="", level="", message="")
        with self.assertRaises(AttributeError):
            entry.level = "ERROR"  # type: ignore[misc]


class TestParseResult(unittest.TestCase):
    """Tests for ParseResult."""

    def test_success_rate_zero(self) -> None:
        r = ParseResult()
        self.assertEqual(r.success_rate, 0.0)

    def test_success_rate(self) -> None:
        r = ParseResult(total_lines=10, parsed_lines=8)
        self.assertAlmostEqual(r.success_rate, 0.8)


class TestLogParser(unittest.TestCase):
    """Tests for LogParser."""

    def setUp(self) -> None:
        self.parser = LogParser()

    # -- Format detection --------------------------------------------------

    def test_detect_json(self) -> None:
        line = json.dumps({"timestamp": "2026-01-01", "level": "INFO", "message": "hi"})
        self.assertEqual(self.parser.detect_format(line), LogFormat.JSON)

    def test_detect_syslog(self) -> None:
        line = "Jan  5 12:34:56 myhost sshd[1234]: Accepted password for user"
        self.assertEqual(self.parser.detect_format(line), LogFormat.SYSLOG)

    def test_detect_unknown(self) -> None:
        self.assertEqual(self.parser.detect_format("just some text"), LogFormat.UNKNOWN)

    def test_detect_empty(self) -> None:
        self.assertEqual(self.parser.detect_format(""), LogFormat.UNKNOWN)

    def test_detect_custom(self) -> None:
        self.parser.add_custom_pattern("myapp", r"^(?P<timestamp>\d{4}-\d{2}-\d{2}) (?P<level>\w+) (?P<message>.*)$")
        self.assertEqual(self.parser.detect_format("2026-01-01 INFO hello"), LogFormat.CUSTOM)

    # -- JSON parsing ------------------------------------------------------

    def test_parse_json_line(self) -> None:
        line = json.dumps({"timestamp": "2026-01-01T00:00:00", "level": "ERROR", "message": "fail", "service": "api"})
        entry = self.parser.parse_line(line, line_number=1)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.level, "ERROR")
        self.assertEqual(entry.message, "fail")
        self.assertEqual(entry.source, "api")
        self.assertEqual(entry.format, LogFormat.JSON)

    def test_parse_json_alt_keys(self) -> None:
        line = json.dumps({"time": "2026-01-01", "severity": "warn", "msg": "slow", "logger": "db"})
        entry = self.parser.parse_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.level, "WARN")
        self.assertEqual(entry.message, "slow")
        self.assertEqual(entry.source, "db")

    def test_parse_json_extra_fields(self) -> None:
        line = json.dumps({"timestamp": "t", "level": "INFO", "message": "m", "request_id": "abc"})
        entry = self.parser.parse_line(line)
        self.assertIn("request_id", entry.fields)
        self.assertEqual(entry.fields["request_id"], "abc")

    def test_parse_json_non_dict(self) -> None:
        entry = self.parser.parse_line(json.dumps([1, 2, 3]))
        # Falls back to unknown
        self.assertIsNotNone(entry)

    # -- Syslog parsing ----------------------------------------------------

    def test_parse_syslog_line(self) -> None:
        line = "Jan  5 12:34:56 myhost sshd[1234]: Accepted password for user"
        entry = self.parser.parse_line(line, line_number=5)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.format, LogFormat.SYSLOG)
        self.assertEqual(entry.source, "sshd")
        self.assertIn("pid", entry.fields)
        self.assertEqual(entry.fields["pid"], "1234")
        self.assertEqual(entry.line_number, 5)

    def test_parse_syslog_without_pid(self) -> None:
        line = "Mar 10 08:00:00 server kernel: Boot complete"
        entry = self.parser.parse_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.source, "kernel")

    def test_parse_syslog_with_level_in_message(self) -> None:
        line = "Jan  1 00:00:00 host app[1]: ERROR something broke"
        entry = self.parser.parse_line(line)
        self.assertEqual(entry.level, "ERROR")

    # -- Custom parsing ----------------------------------------------------

    def test_parse_custom(self) -> None:
        self.parser.add_custom_pattern(
            "myapp",
            r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}) (?P<level>\w+) (?P<source>\w+) (?P<message>.*)$",
        )
        line = "2026-01-01T12:00:00 ERROR api Request failed"
        entry = self.parser.parse_line(line)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.format, LogFormat.CUSTOM)
        self.assertEqual(entry.level, "ERROR")
        self.assertEqual(entry.source, "api")
        self.assertEqual(entry.message, "Request failed")

    # -- Unknown parsing ---------------------------------------------------

    def test_parse_unknown_with_level(self) -> None:
        entry = self.parser.parse_line("something ERROR happened here")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.level, "ERROR")
        self.assertEqual(entry.format, LogFormat.UNKNOWN)

    def test_parse_unknown_no_level(self) -> None:
        entry = self.parser.parse_line("just plain text")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.level, "")

    # -- Multi-line parsing ------------------------------------------------

    def test_parse_multiline(self) -> None:
        text = "\n".join([
            json.dumps({"timestamp": "t1", "level": "INFO", "message": "a"}),
            json.dumps({"timestamp": "t2", "level": "ERROR", "message": "b"}),
            "",
            json.dumps({"timestamp": "t3", "level": "DEBUG", "message": "c"}),
        ])
        result = self.parser.parse(text)
        self.assertEqual(result.total_lines, 4)
        self.assertEqual(result.parsed_lines, 3)
        self.assertEqual(len(result.entries), 3)
        self.assertEqual(result.format_detected, LogFormat.JSON)

    def test_parse_empty(self) -> None:
        result = self.parser.parse("")
        self.assertEqual(result.total_lines, 0)
        self.assertEqual(result.parsed_lines, 0)

    # -- Empty line --------------------------------------------------------

    def test_parse_line_empty(self) -> None:
        self.assertIsNone(self.parser.parse_line(""))
        self.assertIsNone(self.parser.parse_line("   "))

    # -- Field extraction --------------------------------------------------

    def test_extract_fields(self) -> None:
        entry = LogEntry(timestamp="", level="INFO", message="User id=42 logged in from ip=1.2.3.4")
        result = self.parser.extract_fields(entry, r"id=(?P<user_id>\d+).*ip=(?P<ip>[\d.]+)")
        self.assertEqual(result["user_id"], "42")
        self.assertEqual(result["ip"], "1.2.3.4")

    def test_extract_fields_no_match(self) -> None:
        entry = LogEntry(timestamp="", level="INFO", message="no match here")
        result = self.parser.extract_fields(entry, r"id=(?P<user_id>\d+)")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
