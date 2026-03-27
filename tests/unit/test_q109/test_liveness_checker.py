"""Tests for src/lidco/liveness/checker.py."""
import pytest

from lidco.liveness.checker import (
    CheckError,
    CheckResult,
    CheckStatus,
    HealthReport,
    LivenessChecker,
)


def _up_check(name="svc") -> CheckResult:
    return CheckResult(name=name, status=CheckStatus.UP, latency_ms=1.0)


def _down_check(name="svc") -> CheckResult:
    return CheckResult(name=name, status=CheckStatus.DOWN, latency_ms=0.5, message="refused")


class TestCheckResult:
    def test_is_up_true(self):
        r = CheckResult(name="x", status=CheckStatus.UP)
        assert r.is_up is True

    def test_is_up_false(self):
        r = CheckResult(name="x", status=CheckStatus.DOWN)
        assert r.is_up is False

    def test_format_contains_name(self):
        r = CheckResult(name="db", status=CheckStatus.UP, latency_ms=12.5)
        assert "db" in r.format()

    def test_format_contains_status(self):
        r = CheckResult(name="db", status=CheckStatus.DOWN, message="refused")
        assert "down" in r.format()

    def test_format_with_message(self):
        r = CheckResult(name="db", status=CheckStatus.DOWN, message="refused")
        assert "refused" in r.format()


class TestHealthReport:
    def test_all_up_true(self):
        report = HealthReport()
        report.results = [_up_check("a"), _up_check("b")]
        report.finished_at = report.started_at
        assert report.all_up is True

    def test_all_up_false(self):
        report = HealthReport()
        report.results = [_up_check(), _down_check()]
        report.finished_at = report.started_at
        assert report.all_up is False

    def test_up_count(self):
        report = HealthReport()
        report.results = [_up_check(), _up_check(), _down_check()]
        assert report.up_count == 2

    def test_down_count(self):
        report = HealthReport()
        report.results = [_up_check(), _down_check()]
        assert report.down_count == 1

    def test_summary_healthy(self):
        report = HealthReport()
        report.results = [_up_check()]
        report.finished_at = report.started_at
        assert "HEALTHY" in report.summary()

    def test_summary_degraded(self):
        report = HealthReport()
        report.results = [_down_check()]
        report.finished_at = report.started_at
        assert "DEGRADED" in report.summary()

    def test_format(self):
        report = HealthReport()
        report.results = [_up_check("api"), _down_check("db")]
        report.finished_at = report.started_at
        text = report.format()
        assert "api" in text
        assert "db" in text


class TestLivenessChecker:
    def test_init_default_timeout(self):
        checker = LivenessChecker()
        assert checker._timeout > 0

    def test_init_invalid_timeout(self):
        with pytest.raises(CheckError):
            LivenessChecker(timeout=0)

    def test_add_custom(self):
        checker = LivenessChecker()
        checker.add_custom("svc", lambda: _up_check("svc"))
        assert "svc" in checker.list_checks()

    def test_add_custom_empty_name(self):
        checker = LivenessChecker()
        with pytest.raises(CheckError):
            checker.add_custom("", lambda: _up_check())

    def test_add_http_registers(self):
        checker = LivenessChecker()
        checker.add_http("api", "http://localhost/health")
        assert "api" in checker.list_checks()

    def test_add_http_empty_name(self):
        checker = LivenessChecker()
        with pytest.raises(CheckError):
            checker.add_http("", "http://localhost")

    def test_add_tcp_registers(self):
        checker = LivenessChecker()
        checker.add_tcp("db", "localhost", 5432)
        assert "db" in checker.list_checks()

    def test_add_tcp_invalid_port(self):
        checker = LivenessChecker()
        with pytest.raises(CheckError):
            checker.add_tcp("bad", "localhost", 99999)

    def test_add_tcp_empty_name(self):
        checker = LivenessChecker()
        with pytest.raises(CheckError):
            checker.add_tcp("", "localhost", 80)

    def test_remove_existing(self):
        checker = LivenessChecker()
        checker.add_custom("x", lambda: _up_check())
        assert checker.remove("x") is True
        assert "x" not in checker.list_checks()

    def test_remove_nonexistent(self):
        checker = LivenessChecker()
        assert checker.remove("ghost") is False

    def test_len(self):
        checker = LivenessChecker()
        checker.add_custom("a", lambda: _up_check())
        checker.add_custom("b", lambda: _up_check())
        assert len(checker) == 2

    def test_run_known_check(self):
        checker = LivenessChecker()
        checker.add_custom("ok", lambda: _up_check("ok"))
        result = checker.run("ok")
        assert result.is_up is True

    def test_run_unknown_raises(self):
        checker = LivenessChecker()
        with pytest.raises(CheckError):
            checker.run("ghost")

    def test_run_all_returns_report(self):
        checker = LivenessChecker()
        checker.add_custom("a", lambda: _up_check("a"))
        checker.add_custom("b", lambda: _down_check("b"))
        report = checker.run_all()
        assert isinstance(report, HealthReport)
        assert len(report.results) == 2

    def test_run_all_empty(self):
        checker = LivenessChecker()
        report = checker.run_all()
        assert report.all_up is True  # vacuously true

    def test_run_parallel(self):
        checker = LivenessChecker()
        checker.add_custom("x", lambda: _up_check("x"))
        checker.add_custom("y", lambda: _up_check("y"))
        report = checker.run_parallel()
        assert len(report.results) == 2

    def test_tcp_check_closed_port(self):
        checker = LivenessChecker(timeout=0.2)
        checker.add_tcp("closed", "127.0.0.1", 19999)
        result = checker.run("closed")
        assert result.status in (CheckStatus.DOWN, CheckStatus.TIMEOUT)

    def test_with_defaults_has_checks(self):
        checker = LivenessChecker.with_defaults(timeout=0.1)
        assert len(checker) > 0

    def test_with_defaults_has_redis(self):
        checker = LivenessChecker.with_defaults()
        assert "redis" in checker.list_checks()

    def test_custom_check_down(self):
        checker = LivenessChecker()
        checker.add_custom("fail", lambda: _down_check("fail"))
        result = checker.run("fail")
        assert result.is_up is False
        assert result.message == "refused"
