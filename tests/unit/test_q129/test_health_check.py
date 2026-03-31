"""Tests for lidco.telemetry.health_check."""
from lidco.telemetry.health_check import HealthCheck, HealthRegistry, HealthStatus


class TestHealthStatus:
    def test_fields(self):
        s = HealthStatus(name="db", healthy=True, message="OK")
        assert s.name == "db"
        assert s.healthy is True
        assert s.details == {}

    def test_defaults(self):
        s = HealthStatus(name="x", healthy=False)
        assert s.message == ""


class TestHealthCheck:
    def test_passing_check(self):
        check = HealthCheck("ok", lambda: True)
        status = check.run()
        assert status.healthy is True
        assert status.name == "ok"

    def test_failing_check(self):
        check = HealthCheck("fail", lambda: False)
        status = check.run()
        assert status.healthy is False

    def test_exception_makes_unhealthy(self):
        def bad():
            raise RuntimeError("boom")
        check = HealthCheck("boom", bad)
        status = check.run()
        assert status.healthy is False
        assert "boom" in status.message

    def test_name_property(self):
        check = HealthCheck("mycheck", lambda: True)
        assert check.name == "mycheck"

    def test_description(self):
        check = HealthCheck("x", lambda: True, description="Checks X")
        assert check.description == "Checks X"

    def test_message_on_pass(self):
        check = HealthCheck("ok", lambda: True)
        status = check.run()
        assert status.message != ""


class TestHealthRegistry:
    def setup_method(self):
        self.reg = HealthRegistry()

    def test_register_and_run(self):
        self.reg.register(HealthCheck("a", lambda: True))
        statuses = self.reg.run_all()
        assert len(statuses) == 1

    def test_run_all_empty(self):
        assert self.reg.run_all() == []

    def test_is_healthy_all_pass(self):
        self.reg.register(HealthCheck("a", lambda: True))
        self.reg.register(HealthCheck("b", lambda: True))
        assert self.reg.is_healthy() is True

    def test_is_healthy_one_fails(self):
        self.reg.register(HealthCheck("a", lambda: True))
        self.reg.register(HealthCheck("b", lambda: False))
        assert self.reg.is_healthy() is False

    def test_is_healthy_empty_true(self):
        assert self.reg.is_healthy() is True

    def test_summary_all_healthy(self):
        self.reg.register(HealthCheck("a", lambda: True))
        self.reg.register(HealthCheck("b", lambda: True))
        s = self.reg.summary()
        assert s["healthy"] == 2
        assert s["unhealthy"] == 0

    def test_summary_mixed(self):
        self.reg.register(HealthCheck("a", lambda: True))
        self.reg.register(HealthCheck("b", lambda: False))
        s = self.reg.summary()
        assert s["healthy"] == 1
        assert s["unhealthy"] == 1

    def test_names(self):
        self.reg.register(HealthCheck("x", lambda: True))
        self.reg.register(HealthCheck("y", lambda: True))
        assert set(self.reg.names()) == {"x", "y"}

    def test_run_all_returns_correct_names(self):
        self.reg.register(HealthCheck("check1", lambda: True))
        statuses = self.reg.run_all()
        assert statuses[0].name == "check1"

    def test_overwrite_check(self):
        self.reg.register(HealthCheck("a", lambda: True))
        self.reg.register(HealthCheck("a", lambda: False))
        statuses = self.reg.run_all()
        assert statuses[0].healthy is False

    def test_summary_empty(self):
        s = self.reg.summary()
        assert s["healthy"] == 0
        assert s["unhealthy"] == 0

    def test_exception_check_counted_unhealthy(self):
        def raises():
            raise ValueError("bad")
        self.reg.register(HealthCheck("err", raises))
        s = self.reg.summary()
        assert s["unhealthy"] == 1
