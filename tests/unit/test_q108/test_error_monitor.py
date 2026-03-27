"""Tests for src/lidco/monitoring/error_monitor.py."""
import pytest

from lidco.monitoring.error_monitor import (
    ErrorEvent,
    ErrorMonitor,
    ErrorPattern,
    MonitorError,
    Severity,
)


class TestErrorPattern:
    def test_compile_valid(self):
        p = ErrorPattern(id="e", pattern=r"Error:")
        compiled = p.compile()
        assert compiled.search("ValueError: bad") is not None

    def test_compile_invalid_raises(self):
        import re
        with pytest.raises(re.error):
            ErrorPattern(id="e", pattern=r"[invalid").compile()

    def test_id_required_by_monitor(self):
        monitor = ErrorMonitor()
        with pytest.raises(MonitorError):
            monitor.add_pattern(ErrorPattern(id="", pattern=r"x"))


class TestErrorMonitor:
    def test_add_and_list_patterns(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="err", pattern=r"Error"))
        assert any(p.id == "err" for p in monitor.list_patterns())

    def test_remove_pattern(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="x", pattern=r"x"))
        assert monitor.remove_pattern("x") is True
        assert not any(p.id == "x" for p in monitor.list_patterns())

    def test_remove_nonexistent(self):
        monitor = ErrorMonitor()
        assert monitor.remove_pattern("ghost") is False

    def test_feed_line_match(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="err", pattern=r"Error"))
        events = monitor.feed_line("TypeError: bad value")
        assert len(events) == 1
        assert events[0].pattern_id == "err"

    def test_feed_line_no_match(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="err", pattern=r"Exception"))
        events = monitor.feed_line("INFO: all good")
        assert events == []

    def test_feed_line_stores_event(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"Error"))
        monitor.feed_line("Error found")
        assert monitor.event_count() == 1

    def test_feed_lines(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"Error"))
        events = monitor.feed_lines(["Error 1", "ok", "Error 2"])
        assert len(events) == 2

    def test_handler_called(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"Error"))
        captured = []
        monitor.add_handler("e", lambda ev: captured.append(ev))
        monitor.feed_line("Error!")
        assert len(captured) == 1

    def test_on_error_decorator(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"Error"))
        seen = []

        @monitor.on_error("e")
        def h(ev):
            seen.append(ev)

        monitor.feed_line("Error!")
        assert len(seen) == 1

    def test_global_handler(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"Error"))
        all_events = []
        monitor.add_global_handler(lambda ev: all_events.append(ev))
        monitor.feed_line("Error!")
        assert len(all_events) == 1

    def test_events_filter_by_pattern(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="a", pattern=r"AAA"))
        monitor.add_pattern(ErrorPattern(id="b", pattern=r"BBB"))
        monitor.feed_line("AAA")
        monitor.feed_line("BBB")
        a_events = monitor.events(pattern_id="a")
        assert all(e.pattern_id == "a" for e in a_events)

    def test_events_filter_by_severity(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"Error", severity=Severity.ERROR))
        monitor.add_pattern(ErrorPattern(id="w", pattern=r"Warn", severity=Severity.WARNING))
        monitor.feed_line("Error!")
        monitor.feed_line("Warn!")
        errors = monitor.events(severity=Severity.ERROR)
        assert all(e.severity == Severity.ERROR for e in errors)

    def test_events_limit(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"x"))
        for _ in range(10):
            monitor.feed_line("xxx")
        assert len(monitor.events(limit=3)) == 3

    def test_clear_events(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"Error"))
        monitor.feed_line("Error!")
        monitor.clear_events()
        assert monitor.event_count() == 0

    def test_max_events_enforced(self):
        monitor = ErrorMonitor(max_events=5)
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"x"))
        for _ in range(10):
            monitor.feed_line("xxx")
        assert monitor.event_count() <= 5

    def test_event_format(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"Error"))
        events = monitor.feed_line("Error found here")
        assert "ERROR" in events[0].format()
        assert "Error" in events[0].format()

    def test_event_age_seconds(self):
        monitor = ErrorMonitor()
        monitor.add_pattern(ErrorPattern(id="e", pattern=r"x"))
        events = monitor.feed_line("x")
        assert events[0].age_seconds() >= 0

    def test_with_defaults_has_patterns(self):
        monitor = ErrorMonitor.with_defaults()
        assert len(monitor.list_patterns()) > 0

    def test_with_defaults_catches_traceback(self):
        monitor = ErrorMonitor.with_defaults()
        events = monitor.feed_line("Traceback (most recent call last):")
        assert any(e.pattern_id == "traceback" for e in events)

    def test_with_defaults_catches_import_error(self):
        monitor = ErrorMonitor.with_defaults()
        events = monitor.feed_line("ImportError: No module named 'foo'")
        assert len(events) > 0

    def test_with_defaults_catches_http_error(self):
        monitor = ErrorMonitor.with_defaults()
        events = monitor.feed_line("GET /api HTTP 404 Not Found")
        assert any(e.pattern_id == "http-error" for e in events)

    def test_summary_counts(self):
        monitor = ErrorMonitor.with_defaults()
        monitor.feed_lines([
            "TypeError: bad",
            "ImportError: missing",
        ])
        s = monitor.summary()
        assert "error" in s
        total = sum(s.values())
        assert total >= 2

    def test_feed_file(self, tmp_path):
        log_file = tmp_path / "app.log"
        log_file.write_text("TypeError: bad\nINFO: ok\n")
        monitor = ErrorMonitor.with_defaults()
        events = monitor.feed_file(log_file)
        assert len(events) > 0

    def test_feed_file_not_found(self):
        monitor = ErrorMonitor()
        with pytest.raises(MonitorError):
            monitor.feed_file("/nonexistent/path.log")
