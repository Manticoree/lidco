"""Tests for lidco.mesh.circuit_config — CircuitConfigGenerator."""

from __future__ import annotations

import unittest

from lidco.mesh.circuit_config import (
    CircuitBreakerConfig,
    CircuitConfigGenerator,
    CircuitConfigReport,
    FailureRecord,
)


class TestCircuitBreakerConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = CircuitBreakerConfig(service="api")
        self.assertEqual(cfg.failure_threshold, 5)
        self.assertEqual(cfg.recovery_timeout_s, 30.0)
        self.assertEqual(cfg.half_open_max_calls, 3)
        self.assertEqual(cfg.error_rate_threshold, 0.5)

    def test_frozen(self) -> None:
        cfg = CircuitBreakerConfig(service="api")
        with self.assertRaises(AttributeError):
            cfg.service = "x"  # type: ignore[misc]


class TestFailureRecord(unittest.TestCase):
    def test_creation(self) -> None:
        rec = FailureRecord(service="api", timestamp=1.0, error_type="timeout")
        self.assertEqual(rec.service, "api")
        self.assertEqual(rec.error_type, "timeout")


class TestCircuitConfigGenerator(unittest.TestCase):
    def test_empty_generate(self) -> None:
        gen = CircuitConfigGenerator()
        report = gen.generate()
        self.assertEqual(len(report.configs), 0)
        self.assertIn("No failure data", report.recommendations[0])

    def test_generate_default_config(self) -> None:
        gen = CircuitConfigGenerator()
        gen.add_failure(FailureRecord(service="api", timestamp=1.0))
        report = gen.generate()
        self.assertEqual(len(report.configs), 1)
        self.assertEqual(report.configs[0].service, "api")

    def test_generate_for_service_defaults(self) -> None:
        gen = CircuitConfigGenerator()
        cfg = gen.generate_for_service("api")
        self.assertEqual(cfg.service, "api")
        self.assertEqual(cfg.failure_threshold, 5)

    def test_high_failure_count_tunes_aggressively(self) -> None:
        gen = CircuitConfigGenerator()
        for i in range(25):
            gen.add_failure(FailureRecord(service="flaky", timestamp=float(i)))
        cfg = gen.generate_for_service("flaky")
        self.assertLess(cfg.failure_threshold, 5)
        self.assertGreater(cfg.recovery_timeout_s, 30.0)
        self.assertLess(cfg.error_rate_threshold, 0.5)

    def test_medium_failure_count(self) -> None:
        gen = CircuitConfigGenerator()
        for i in range(15):
            gen.add_failure(FailureRecord(service="medium", timestamp=float(i)))
        cfg = gen.generate_for_service("medium")
        self.assertLessEqual(cfg.failure_threshold, 5)

    def test_slow_failures_tune_slow_call(self) -> None:
        gen = CircuitConfigGenerator()
        for i in range(25):
            gen.add_failure(FailureRecord(
                service="slow", timestamp=float(i), duration_ms=10000.0
            ))
        cfg = gen.generate_for_service("slow")
        self.assertLess(cfg.slow_call_duration_ms, 10000.0)
        self.assertEqual(cfg.slow_call_rate_threshold, 0.3)

    def test_overrides_applied(self) -> None:
        gen = CircuitConfigGenerator()
        gen.add_failure(FailureRecord(service="api", timestamp=1.0))
        gen.set_override("api", failure_threshold=10, recovery_timeout_s=60.0)
        cfg = gen.generate_for_service("api")
        self.assertEqual(cfg.failure_threshold, 10)
        self.assertEqual(cfg.recovery_timeout_s, 60.0)

    def test_generate_with_explicit_services(self) -> None:
        gen = CircuitConfigGenerator()
        gen.add_failure(FailureRecord(service="a", timestamp=1.0))
        report = gen.generate(services=["a", "b"])
        names = {c.service for c in report.configs}
        self.assertEqual(names, {"a", "b"})

    def test_failure_count_property(self) -> None:
        gen = CircuitConfigGenerator()
        self.assertEqual(gen.failure_count, 0)
        gen.add_failures([
            FailureRecord(service="a", timestamp=1.0),
            FailureRecord(service="b", timestamp=2.0),
        ])
        self.assertEqual(gen.failure_count, 2)

    def test_recommendations_for_high_failure(self) -> None:
        gen = CircuitConfigGenerator()
        for i in range(25):
            gen.add_failure(FailureRecord(service="bad", timestamp=float(i)))
        report = gen.generate()
        self.assertTrue(any("bad" in r for r in report.recommendations))

    def test_custom_defaults(self) -> None:
        defaults = CircuitBreakerConfig(
            service="__default__", failure_threshold=10, recovery_timeout_s=60.0
        )
        gen = CircuitConfigGenerator(defaults=defaults)
        cfg = gen.generate_for_service("svc")
        self.assertEqual(cfg.failure_threshold, 10)
        self.assertEqual(cfg.recovery_timeout_s, 60.0)


if __name__ == "__main__":
    unittest.main()
