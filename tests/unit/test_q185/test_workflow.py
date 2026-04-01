"""Tests for feature_dev.workflow — FeatureDevWorkflow."""
from __future__ import annotations

import unittest

from lidco.feature_dev.phases import Phase, PhaseConfig, PhaseStatus
from lidco.feature_dev.workflow import FeatureDevWorkflow, WorkflowError


class TestWorkflowInit(unittest.TestCase):
    def test_basic_creation(self):
        wf = FeatureDevWorkflow("cache", "Add caching layer")
        self.assertEqual(wf.name, "cache")
        self.assertEqual(wf.description, "Add caching layer")

    def test_empty_name_raises(self):
        with self.assertRaises(WorkflowError):
            FeatureDevWorkflow("", "desc")

    def test_whitespace_name_raises(self):
        with self.assertRaises(WorkflowError):
            FeatureDevWorkflow("   ", "desc")

    def test_initial_state(self):
        wf = FeatureDevWorkflow("x", "y")
        self.assertFalse(wf.is_complete)
        self.assertEqual(wf.history, ())
        self.assertEqual(wf.current_phase, Phase.DISCOVERY)


class TestRunPhase(unittest.TestCase):
    def test_run_single_phase(self):
        wf = FeatureDevWorkflow("feat", "desc")
        result = wf.run_phase(Phase.DISCOVERY)
        self.assertEqual(result.phase, Phase.DISCOVERY)
        self.assertEqual(result.status, PhaseStatus.DONE)
        self.assertIn("feat", result.output)
        self.assertGreaterEqual(result.duration_ms, 0)

    def test_run_phase_advances_current(self):
        wf = FeatureDevWorkflow("feat", "desc")
        wf.run_phase(Phase.DISCOVERY)
        self.assertEqual(wf.current_phase, Phase.EXPLORATION)

    def test_run_phase_appends_history(self):
        wf = FeatureDevWorkflow("feat", "desc")
        wf.run_phase(Phase.DISCOVERY)
        self.assertEqual(len(wf.history), 1)
        self.assertEqual(wf.history[0].phase, Phase.DISCOVERY)

    def test_run_phase_duration_non_negative(self):
        wf = FeatureDevWorkflow("feat", "desc")
        result = wf.run_phase(Phase.DISCOVERY)
        self.assertGreaterEqual(result.duration_ms, 0)


class TestRunAll(unittest.TestCase):
    def test_runs_all_seven(self):
        wf = FeatureDevWorkflow("feat", "desc")
        results = wf.run_all()
        self.assertEqual(len(results), 7)
        self.assertTrue(wf.is_complete)

    def test_all_phases_done(self):
        wf = FeatureDevWorkflow("feat", "desc")
        results = wf.run_all()
        for r in results:
            self.assertIn(r.status, (PhaseStatus.DONE, PhaseStatus.SKIPPED))

    def test_history_matches_results(self):
        wf = FeatureDevWorkflow("feat", "desc")
        results = wf.run_all()
        self.assertEqual(len(wf.history), 7)
        self.assertEqual(results, wf.history)

    def test_run_all_after_partial(self):
        wf = FeatureDevWorkflow("feat", "desc")
        wf.run_phase(Phase.DISCOVERY)
        remaining = wf.run_all()
        self.assertEqual(len(remaining), 6)
        self.assertTrue(wf.is_complete)


class TestSkipPhase(unittest.TestCase):
    def test_skip_returns_new_instance(self):
        wf = FeatureDevWorkflow("feat", "desc")
        wf2 = wf.skip_phase(Phase.CLARIFICATION)
        self.assertIsNot(wf, wf2)

    def test_skipped_phase_in_run_all(self):
        wf = FeatureDevWorkflow("feat", "desc")
        wf = wf.skip_phase(Phase.CLARIFICATION)
        results = wf.run_all()
        clar = [r for r in results if r.phase == Phase.CLARIFICATION]
        self.assertEqual(len(clar), 1)
        self.assertEqual(clar[0].status, PhaseStatus.SKIPPED)
        self.assertEqual(clar[0].duration_ms, 0)

    def test_skip_preserves_name(self):
        wf = FeatureDevWorkflow("my-feat", "my-desc")
        wf2 = wf.skip_phase(Phase.REVIEW)
        self.assertEqual(wf2.name, "my-feat")
        self.assertEqual(wf2.description, "my-desc")


class TestCurrentPhase(unittest.TestCase):
    def test_starts_at_discovery(self):
        wf = FeatureDevWorkflow("f", "d")
        self.assertEqual(wf.current_phase, Phase.DISCOVERY)

    def test_after_complete_returns_last(self):
        wf = FeatureDevWorkflow("f", "d")
        wf.run_all()
        self.assertEqual(wf.current_phase, Phase.SUMMARY)


class TestIsComplete(unittest.TestCase):
    def test_not_complete_initially(self):
        wf = FeatureDevWorkflow("f", "d")
        self.assertFalse(wf.is_complete)

    def test_complete_after_run_all(self):
        wf = FeatureDevWorkflow("f", "d")
        wf.run_all()
        self.assertTrue(wf.is_complete)


class TestCustomConfigs(unittest.TestCase):
    def test_custom_config_used(self):
        custom = {Phase.DISCOVERY: PhaseConfig(max_agents=5, timeout_s=10.0, required=False)}
        wf = FeatureDevWorkflow("f", "d", configs=custom)
        # Workflow should still run normally
        result = wf.run_phase(Phase.DISCOVERY)
        self.assertEqual(result.status, PhaseStatus.DONE)


if __name__ == "__main__":
    unittest.main()
