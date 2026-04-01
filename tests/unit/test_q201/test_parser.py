"""Tests for lidco.cron.parser."""

from __future__ import annotations

from datetime import datetime

import pytest

from lidco.cron.parser import CronExpression, CronField, CronParseError, CronParser


@pytest.fixture
def parser() -> CronParser:
    return CronParser()


class TestCronParser:
    def test_parse_every_five_minutes(self, parser: CronParser) -> None:
        expr = parser.parse("*/5 * * * *")
        assert 0 in expr.minute.values
        assert 5 in expr.minute.values
        assert 10 in expr.minute.values
        assert 3 not in expr.minute.values

    def test_parse_specific_values(self, parser: CronParser) -> None:
        expr = parser.parse("30 14 * * *")
        assert expr.minute.values == frozenset({30})
        assert expr.hour.values == frozenset({14})

    def test_parse_range(self, parser: CronParser) -> None:
        expr = parser.parse("* 9-17 * * *")
        assert expr.hour.values == frozenset(range(9, 18))

    def test_parse_list(self, parser: CronParser) -> None:
        expr = parser.parse("0,15,30,45 * * * *")
        assert expr.minute.values == frozenset({0, 15, 30, 45})

    def test_parse_combined_range_and_step(self, parser: CronParser) -> None:
        expr = parser.parse("1-10/2 * * * *")
        assert expr.minute.values == frozenset({1, 3, 5, 7, 9})

    def test_parse_invalid_field_count(self, parser: CronParser) -> None:
        with pytest.raises(CronParseError, match="Expected 5 fields"):
            parser.parse("* * *")

    def test_parse_invalid_value(self, parser: CronParser) -> None:
        with pytest.raises(CronParseError):
            parser.parse("60 * * * *")

    def test_validate_returns_errors(self, parser: CronParser) -> None:
        errors = parser.validate("99 * * * *")
        assert len(errors) > 0
        assert any("out of bounds" in e for e in errors)

    def test_validate_valid_expression(self, parser: CronParser) -> None:
        errors = parser.validate("*/10 * * * *")
        assert errors == []

    def test_describe(self, parser: CronParser) -> None:
        expr = parser.parse("30 14 * * *")
        desc = expr.describe()
        assert "minute=30" in desc
        assert "hour=14" in desc
        assert "every day" in desc

    def test_matches(self, parser: CronParser) -> None:
        expr = parser.parse("30 14 * * *")
        dt_match = datetime(2026, 4, 1, 14, 30, 0)
        dt_no_match = datetime(2026, 4, 1, 14, 31, 0)
        assert expr.matches(dt_match)
        assert not expr.matches(dt_no_match)

    def test_next_run(self, parser: CronParser) -> None:
        expr = parser.parse("0 * * * *")
        base = datetime(2026, 4, 1, 10, 30, 0)
        nxt = expr.next_run(base)
        assert nxt.minute == 0
        assert nxt.hour == 11

    def test_parse_day_of_week(self, parser: CronParser) -> None:
        # 1 = Monday in cron (cron: 0=Sun, 1=Mon)
        expr = parser.parse("0 9 * * 1")
        # Monday is Python weekday 0; cron 1 maps to Python 0
        dt_mon = datetime(2026, 4, 6, 9, 0, 0)  # 2026-04-06 is a Monday
        assert expr.matches(dt_mon)

    def test_parse_field_invalid_step(self, parser: CronParser) -> None:
        with pytest.raises(CronParseError, match="Invalid step"):
            parser.parse_field("*/0", 0, 59)
