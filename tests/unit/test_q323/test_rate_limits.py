"""Tests for lidco.mesh.rate_limits — RateLimitGenerator."""

from __future__ import annotations

import unittest

from lidco.mesh.rate_limits import (
    EndpointCapacity,
    PriorityLane,
    RateLimitConfig,
    RateLimitGenerator,
    RateLimitReport,
)


class TestPriorityLane(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(PriorityLane.CRITICAL.value, "critical")
        self.assertEqual(PriorityLane.NORMAL.value, "normal")
        self.assertEqual(PriorityLane.BACKGROUND.value, "background")


class TestEndpointCapacity(unittest.TestCase):
    def test_defaults(self) -> None:
        cap = EndpointCapacity(service="api", endpoint="/health", max_rps=100.0)
        self.assertEqual(cap.avg_rps, 0.0)
        self.assertEqual(cap.p99_latency_ms, 0.0)


class TestRateLimitConfig(unittest.TestCase):
    def test_frozen(self) -> None:
        cfg = RateLimitConfig(service="api", endpoint="/", requests_per_second=10, burst_size=20)
        with self.assertRaises(AttributeError):
            cfg.service = "x"  # type: ignore[misc]


class TestRateLimitGenerator(unittest.TestCase):
    def test_empty_generate(self) -> None:
        gen = RateLimitGenerator()
        report = gen.generate()
        self.assertEqual(report.total_endpoints, 0)
        self.assertIn("No capacity data", report.recommendations[0])

    def test_invalid_safety_margin(self) -> None:
        with self.assertRaises(ValueError):
            RateLimitGenerator(safety_margin=0.0)
        with self.assertRaises(ValueError):
            RateLimitGenerator(safety_margin=1.5)

    def test_basic_generation(self) -> None:
        gen = RateLimitGenerator(safety_margin=0.8)
        gen.add_capacity(EndpointCapacity(service="api", endpoint="/users", max_rps=100.0))
        report = gen.generate()
        self.assertEqual(report.total_endpoints, 1)
        cfg = report.configs[0]
        self.assertEqual(cfg.service, "api")
        self.assertEqual(cfg.endpoint, "/users")
        # 100 * 0.8 * 0.8 (normal priority) = 64
        self.assertAlmostEqual(cfg.requests_per_second, 64.0, places=0)
        self.assertGreaterEqual(cfg.burst_size, 1)

    def test_priority_affects_rps(self) -> None:
        gen = RateLimitGenerator(safety_margin=1.0)
        cap = EndpointCapacity(service="api", endpoint="/health", max_rps=100.0)
        gen.add_capacity(cap)

        gen.set_priority("api", "/health", PriorityLane.CRITICAL)
        report = gen.generate()
        critical_rps = report.configs[0].requests_per_second

        gen2 = RateLimitGenerator(safety_margin=1.0)
        gen2.add_capacity(cap)
        gen2.set_priority("api", "/health", PriorityLane.LOW)
        report2 = gen2.generate()
        low_rps = report2.configs[0].requests_per_second

        self.assertGreater(critical_rps, low_rps)

    def test_burst_multiplier(self) -> None:
        gen = RateLimitGenerator()
        gen.set_burst_multiplier(3.0)
        gen.add_capacity(EndpointCapacity(service="api", endpoint="/", max_rps=100.0))
        report = gen.generate()
        cfg = report.configs[0]
        # burst = rps * 3.0
        self.assertGreaterEqual(cfg.burst_size, int(cfg.requests_per_second * 2.5))

    def test_burst_multiplier_validation(self) -> None:
        gen = RateLimitGenerator()
        with self.assertRaises(ValueError):
            gen.set_burst_multiplier(0.5)

    def test_high_latency_retry_after(self) -> None:
        gen = RateLimitGenerator()
        gen.add_capacity(EndpointCapacity(
            service="api", endpoint="/slow", max_rps=50.0, p99_latency_ms=3000.0
        ))
        report = gen.generate()
        self.assertGreater(report.configs[0].retry_after_s, 1.0)

    def test_very_high_latency_retry_after(self) -> None:
        gen = RateLimitGenerator()
        gen.add_capacity(EndpointCapacity(
            service="api", endpoint="/very-slow", max_rps=50.0, p99_latency_ms=6000.0
        ))
        report = gen.generate()
        self.assertEqual(report.configs[0].retry_after_s, 5.0)

    def test_low_capacity_recommendation(self) -> None:
        gen = RateLimitGenerator()
        gen.add_capacity(EndpointCapacity(service="tiny", endpoint="/", max_rps=5.0))
        report = gen.generate()
        self.assertTrue(any("low capacity" in r for r in report.recommendations))

    def test_high_latency_recommendation(self) -> None:
        gen = RateLimitGenerator()
        gen.add_capacity(EndpointCapacity(
            service="slow", endpoint="/", max_rps=100.0, p99_latency_ms=8000.0
        ))
        report = gen.generate()
        self.assertTrue(any("high p99" in r for r in report.recommendations))

    def test_add_capacities(self) -> None:
        gen = RateLimitGenerator()
        gen.add_capacities([
            EndpointCapacity(service="a", endpoint="/1", max_rps=100.0),
            EndpointCapacity(service="b", endpoint="/2", max_rps=200.0),
        ])
        self.assertEqual(gen.endpoint_count, 2)
        report = gen.generate()
        self.assertEqual(report.total_endpoints, 2)

    def test_min_rps_floor(self) -> None:
        gen = RateLimitGenerator(safety_margin=0.8)
        gen.add_capacity(EndpointCapacity(service="api", endpoint="/", max_rps=0.5))
        report = gen.generate()
        self.assertGreaterEqual(report.configs[0].requests_per_second, 1.0)


if __name__ == "__main__":
    unittest.main()
