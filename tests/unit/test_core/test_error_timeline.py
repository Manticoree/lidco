"""Tests for error_timeline.build_timeline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

from lidco.core.error_timeline import build_timeline, _make_bar


# ---------------------------------------------------------------------------
# Mock ErrorRecord
# ---------------------------------------------------------------------------

@dataclass
class MockErrorRecord:
    """Minimal stand-in for ErrorRecord with only the fields build_timeline needs."""
    timestamp: datetime
    error_type: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _record(offset_minutes: int = 0, error_type: str = "tool_error") -> MockErrorRecord:
    """Create a MockErrorRecord offset_minutes minutes before now."""
    ts = _utc_now() - timedelta(minutes=offset_minutes)
    return MockErrorRecord(timestamp=ts, error_type=error_type)


# ---------------------------------------------------------------------------
# _make_bar unit tests
# ---------------------------------------------------------------------------

class TestMakeBar:
    def test_zero_errors_all_empty(self) -> None:
        assert _make_bar(0) == "░░░░░░"

    def test_six_errors_all_filled(self) -> None:
        assert _make_bar(6) == "▓▓▓▓▓▓"

    def test_more_than_six_capped_at_filled(self) -> None:
        assert _make_bar(10) == "▓▓▓▓▓▓"

    def test_partial_fill(self) -> None:
        bar = _make_bar(3)
        assert bar == "▓▓▓░░░"


# ---------------------------------------------------------------------------
# build_timeline
# ---------------------------------------------------------------------------

class TestBuildTimeline:
    def test_empty_records_returns_no_error_data(self) -> None:
        result = build_timeline([])
        assert "No error data" in result

    def test_records_produce_timeline_header(self) -> None:
        records = [_record(2), _record(5)]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
            result = build_timeline(records)
        assert "Error Timeline" in result

    def test_time_bucketing_two_errors_same_window(self) -> None:
        """Two errors within the same 5-min bucket appear as one bucket entry."""
        # Place both records exactly 1 minute apart within the same 5-min window
        now = _utc_now()
        # Align to the start of a 5-min window
        minute_floor = (now.minute // 5) * 5
        base_ts = now.replace(minute=minute_floor, second=0, microsecond=0)
        r1 = MockErrorRecord(timestamp=base_ts, error_type="KeyError")
        r2 = MockErrorRecord(timestamp=base_ts + timedelta(minutes=1), error_type="KeyError")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
            result = build_timeline([r1, r2])
        # The bucket should show 2 errors
        assert "2 errors" in result or "2 error" in result

    def test_bar_chart_uses_filled_symbol_for_errors(self) -> None:
        records = [_record(2)]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
            result = build_timeline(records)
        assert "▓" in result

    def test_error_type_distribution_shown(self) -> None:
        records = [
            _record(2, error_type="AttributeError"),
            _record(3, error_type="KeyError"),
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
            result = build_timeline(records)
        # At least one of the error types should appear in the output
        assert "AttributeError" in result or "KeyError" in result

    def test_zero_errors_in_bucket_uses_empty_bar(self) -> None:
        # Create a record far enough back that there are empty buckets between it
        # and now. We just verify the ░ character appears in the output.
        records = [_record(25)]  # 25 min ago — leaves several empty buckets
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
            result = build_timeline(records)
        assert "░" in result

    def test_six_or_more_errors_all_filled_bar(self) -> None:
        """A bucket with 6 errors shows the fully filled bar ▓▓▓▓▓▓."""
        now = _utc_now()
        minute_floor = (now.minute // 5) * 5
        base_ts = now.replace(minute=minute_floor, second=0, microsecond=0)
        records = [
            MockErrorRecord(timestamp=base_ts + timedelta(seconds=i), error_type="OSError")
            for i in range(6)
        ]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
            result = build_timeline(records)
        assert "▓▓▓▓▓▓" in result

    def test_output_is_non_empty_string(self) -> None:
        records = [_record(1)]
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
            result = build_timeline(records)
        assert isinstance(result, str)
        assert len(result) > 0
