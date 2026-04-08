"""Tests for lidco.dr.tester — DRTestRunner."""

from __future__ import annotations

import unittest

from lidco.dr.tester import (
    DRTestRunner,
    IntegrityResult,
    ScenarioConfig,
    ScenarioType,
    DRTestResult,
    DRTestScenario,
    DRTestStatus,
)


class TestScenarioConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        sc = ScenarioConfig(scenario_type=ScenarioType.FULL_FAILOVER)
        self.assertEqual(sc.timeout_seconds, 300)
        self.assertEqual(sc.chaos_intensity, 0.5)

    def test_invalid_timeout(self) -> None:
        with self.assertRaises(ValueError):
            ScenarioConfig(scenario_type=ScenarioType.CHAOS, timeout_seconds=0)

    def test_invalid_intensity(self) -> None:
        with self.assertRaises(ValueError):
            ScenarioConfig(scenario_type=ScenarioType.CHAOS, chaos_intensity=2.0)


class TestIntegrityResult(unittest.TestCase):
    def test_valid(self) -> None:
        ir = IntegrityResult(component="db", is_valid=True, records_checked=100)
        self.assertTrue(ir.is_valid)
        self.assertEqual(ir.records_checked, 100)

    def test_invalid(self) -> None:
        ir = IntegrityResult(component="db", is_valid=False, records_corrupted=5)
        self.assertFalse(ir.is_valid)


class TestDRTestResult(unittest.TestCase):
    def test_duration(self) -> None:
        tr = DRTestResult(
            test_id="t1",
            scenario_type=ScenarioType.BACKUP_RESTORE,
            status=DRTestStatus.PASSED,
            started_at=100.0,
            completed_at=105.0,
        )
        self.assertAlmostEqual(tr.duration_seconds, 5.0)

    def test_all_integrity_valid(self) -> None:
        tr = DRTestResult(
            test_id="t2",
            scenario_type=ScenarioType.CHAOS,
            status=DRTestStatus.PASSED,
            started_at=0,
            data_integrity=[
                IntegrityResult(component="a", is_valid=True),
                IntegrityResult(component="b", is_valid=True),
            ],
        )
        self.assertTrue(tr.all_integrity_valid)

    def test_integrity_invalid(self) -> None:
        tr = DRTestResult(
            test_id="t3",
            scenario_type=ScenarioType.CHAOS,
            status=DRTestStatus.FAILED,
            started_at=0,
            data_integrity=[
                IntegrityResult(component="a", is_valid=True),
                IntegrityResult(component="b", is_valid=False),
            ],
        )
        self.assertFalse(tr.all_integrity_valid)

    def test_empty_integrity_valid(self) -> None:
        tr = DRTestResult(
            test_id="t4",
            scenario_type=ScenarioType.CHAOS,
            status=DRTestStatus.PASSED,
            started_at=0,
        )
        self.assertTrue(tr.all_integrity_valid)

    def test_to_dict(self) -> None:
        tr = DRTestResult(
            test_id="t5",
            scenario_type=ScenarioType.FULL_FAILOVER,
            status=DRTestStatus.PASSED,
            started_at=100.0,
            completed_at=110.0,
            steps_completed=3,
            steps_total=3,
        )
        d = tr.to_dict()
        self.assertEqual(d["test_id"], "t5")
        self.assertEqual(d["status"], "passed")
        self.assertAlmostEqual(d["duration_seconds"], 10.0)


class TestDRTestRunner(unittest.TestCase):
    def _runner_with_scenario(self) -> tuple[DRTestRunner, str]:
        runner = DRTestRunner()
        config = ScenarioConfig(
            scenario_type=ScenarioType.FULL_FAILOVER,
            name="Test Failover",
        )
        scenario = runner.create_scenario(config)
        scenario.add_step(lambda: True)
        scenario.add_step(lambda: True)
        scenario.add_integrity_check(
            lambda: IntegrityResult(component="db", is_valid=True, records_checked=50)
        )
        return runner, scenario.scenario_id

    def test_create_scenario(self) -> None:
        runner = DRTestRunner()
        config = ScenarioConfig(scenario_type=ScenarioType.CHAOS)
        s = runner.create_scenario(config)
        self.assertIn(s.scenario_id, runner.scenarios)

    def test_get_scenario(self) -> None:
        runner, sid = self._runner_with_scenario()
        self.assertIsNotNone(runner.get_scenario(sid))
        self.assertIsNone(runner.get_scenario("nonexistent"))

    def test_run_scenario_pass(self) -> None:
        runner, sid = self._runner_with_scenario()
        result = runner.run_scenario(sid)
        self.assertEqual(result.status, DRTestStatus.PASSED)
        self.assertEqual(result.steps_completed, 2)
        self.assertEqual(result.steps_total, 2)
        self.assertTrue(result.all_integrity_valid)

    def test_run_scenario_step_fails(self) -> None:
        runner = DRTestRunner()
        config = ScenarioConfig(scenario_type=ScenarioType.PARTIAL_FAILURE)
        s = runner.create_scenario(config)
        s.add_step(lambda: True)
        s.add_step(lambda: False)  # will fail
        s.add_step(lambda: True)
        result = runner.run_scenario(s.scenario_id)
        self.assertEqual(result.status, DRTestStatus.FAILED)
        self.assertEqual(result.steps_completed, 1)
        self.assertIn("Step 2 failed", result.error)

    def test_run_scenario_integrity_fails(self) -> None:
        runner = DRTestRunner()
        config = ScenarioConfig(scenario_type=ScenarioType.DATA_CORRUPTION)
        s = runner.create_scenario(config)
        s.add_step(lambda: True)
        s.add_integrity_check(
            lambda: IntegrityResult(component="x", is_valid=False)
        )
        result = runner.run_scenario(s.scenario_id)
        self.assertEqual(result.status, DRTestStatus.FAILED)
        self.assertIn("integrity", result.error)

    def test_run_scenario_exception(self) -> None:
        runner = DRTestRunner()
        config = ScenarioConfig(scenario_type=ScenarioType.CHAOS)
        s = runner.create_scenario(config)

        def bad_step() -> bool:
            raise RuntimeError("boom")

        s.add_step(bad_step)
        result = runner.run_scenario(s.scenario_id)
        self.assertEqual(result.status, DRTestStatus.ERROR)
        self.assertIn("boom", result.error)

    def test_run_nonexistent_scenario(self) -> None:
        runner = DRTestRunner()
        result = runner.run_scenario("nope")
        self.assertEqual(result.status, DRTestStatus.ERROR)
        self.assertIn("not found", result.error)

    def test_run_all(self) -> None:
        runner = DRTestRunner()
        for st in [ScenarioType.FULL_FAILOVER, ScenarioType.BACKUP_RESTORE]:
            s = runner.create_scenario(ScenarioConfig(scenario_type=st))
            s.add_step(lambda: True)
        results = runner.run_all()
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r.status == DRTestStatus.PASSED for r in results))

    def test_get_summary(self) -> None:
        runner, sid = self._runner_with_scenario()
        runner.run_scenario(sid)
        summary = runner.get_summary()
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["passed"], 1)
        self.assertEqual(summary["failed"], 0)

    def test_compute_checksum(self) -> None:
        c = DRTestRunner.compute_checksum(b"hello")
        self.assertEqual(len(c), 64)  # SHA-256 hex
        self.assertEqual(c, DRTestRunner.compute_checksum(b"hello"))

    def test_results_tracked(self) -> None:
        runner, sid = self._runner_with_scenario()
        runner.run_scenario(sid)
        self.assertEqual(len(runner.results), 1)


if __name__ == "__main__":
    unittest.main()
