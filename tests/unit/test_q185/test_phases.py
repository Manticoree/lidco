"""Tests for feature_dev.phases — Phase, PhaseStatus, PhaseResult, PhaseConfig."""
from __future__ import annotations

import unittest

from lidco.feature_dev.phases import (
    DEFAULT_CONFIGS,
    PHASE_ORDER,
    Phase,
    PhaseConfig,
    PhaseResult,
    PhaseStatus,
)


class TestPhaseEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Phase.DISCOVERY.value, "discovery")
        self.assertEqual(Phase.EXPLORATION.value, "exploration")
        self.assertEqual(Phase.CLARIFICATION.value, "clarification")
        self.assertEqual(Phase.ARCHITECTURE.value, "architecture")
        self.assertEqual(Phase.IMPLEMENTATION.value, "implementation")
        self.assertEqual(Phase.REVIEW.value, "review")
        self.assertEqual(Phase.SUMMARY.value, "summary")

    def test_count(self):
        self.assertEqual(len(Phase), 7)

    def test_is_string_enum(self):
        self.assertIsInstance(Phase.DISCOVERY, str)
        self.assertEqual(f"{Phase.DISCOVERY}", "Phase.DISCOVERY")

    def test_lookup_by_value(self):
        self.assertIs(Phase("discovery"), Phase.DISCOVERY)
        self.assertIs(Phase("summary"), Phase.SUMMARY)


class TestPhaseStatusEnum(unittest.TestCase):
    def test_values(self):
        self.assertEqual(PhaseStatus.PENDING.value, "pending")
        self.assertEqual(PhaseStatus.ACTIVE.value, "active")
        self.assertEqual(PhaseStatus.DONE.value, "done")
        self.assertEqual(PhaseStatus.SKIPPED.value, "skipped")

    def test_count(self):
        self.assertEqual(len(PhaseStatus), 4)


class TestPhaseResult(unittest.TestCase):
    def test_frozen(self):
        r = PhaseResult(
            phase=Phase.DISCOVERY,
            status=PhaseStatus.DONE,
            output="ok",
            duration_ms=42,
        )
        with self.assertRaises(AttributeError):
            r.output = "changed"  # type: ignore[misc]

    def test_fields(self):
        r = PhaseResult(
            phase=Phase.REVIEW,
            status=PhaseStatus.SKIPPED,
            output="skipped review",
            duration_ms=0,
        )
        self.assertEqual(r.phase, Phase.REVIEW)
        self.assertEqual(r.status, PhaseStatus.SKIPPED)
        self.assertEqual(r.output, "skipped review")
        self.assertEqual(r.duration_ms, 0)

    def test_equality(self):
        a = PhaseResult(Phase.SUMMARY, PhaseStatus.DONE, "done", 10)
        b = PhaseResult(Phase.SUMMARY, PhaseStatus.DONE, "done", 10)
        self.assertEqual(a, b)

    def test_different_not_equal(self):
        a = PhaseResult(Phase.SUMMARY, PhaseStatus.DONE, "done", 10)
        b = PhaseResult(Phase.SUMMARY, PhaseStatus.DONE, "done", 20)
        self.assertNotEqual(a, b)


class TestPhaseConfig(unittest.TestCase):
    def test_frozen(self):
        c = PhaseConfig(max_agents=2, timeout_s=30.0, required=True)
        with self.assertRaises(AttributeError):
            c.max_agents = 5  # type: ignore[misc]

    def test_fields(self):
        c = PhaseConfig(max_agents=3, timeout_s=120.0, required=False)
        self.assertEqual(c.max_agents, 3)
        self.assertAlmostEqual(c.timeout_s, 120.0)
        self.assertFalse(c.required)


class TestPhaseOrder(unittest.TestCase):
    def test_is_tuple(self):
        self.assertIsInstance(PHASE_ORDER, tuple)

    def test_length(self):
        self.assertEqual(len(PHASE_ORDER), 7)

    def test_first_last(self):
        self.assertEqual(PHASE_ORDER[0], Phase.DISCOVERY)
        self.assertEqual(PHASE_ORDER[-1], Phase.SUMMARY)

    def test_matches_enum_order(self):
        self.assertEqual(PHASE_ORDER, tuple(Phase))


class TestDefaultConfigs(unittest.TestCase):
    def test_all_phases_covered(self):
        for phase in Phase:
            self.assertIn(phase, DEFAULT_CONFIGS)

    def test_discovery_config(self):
        c = DEFAULT_CONFIGS[Phase.DISCOVERY]
        self.assertEqual(c.max_agents, 1)
        self.assertAlmostEqual(c.timeout_s, 30.0)
        self.assertTrue(c.required)

    def test_clarification_optional(self):
        c = DEFAULT_CONFIGS[Phase.CLARIFICATION]
        self.assertFalse(c.required)

    def test_implementation_has_most_agents(self):
        impl = DEFAULT_CONFIGS[Phase.IMPLEMENTATION]
        self.assertEqual(impl.max_agents, 3)


if __name__ == "__main__":
    unittest.main()
