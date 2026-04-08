"""Tests for lidco.chaos.experiments."""

from __future__ import annotations

import unittest
from unittest import mock

from lidco.chaos.experiments import (
    ChaosExperimentRunner,
    Experiment,
    ExperimentConfig,
    ExperimentResult,
    ExperimentStatus,
    ExperimentType,
)


class TestExperimentConfig(unittest.TestCase):
    def test_create_default_config(self) -> None:
        cfg = ExperimentConfig(experiment_type=ExperimentType.NETWORK_DELAY)
        self.assertEqual(cfg.experiment_type, ExperimentType.NETWORK_DELAY)
        self.assertEqual(cfg.duration_seconds, 30.0)
        self.assertEqual(cfg.scope, "local")
        self.assertEqual(cfg.intensity, 0.5)
        self.assertEqual(cfg.target, "")
        self.assertEqual(cfg.parameters, {})

    def test_create_custom_config(self) -> None:
        cfg = ExperimentConfig(
            experiment_type=ExperimentType.DISK_FULL,
            duration_seconds=60.0,
            scope="global",
            intensity=0.9,
            target="storage-service",
            parameters={"fill_percent": 95},
        )
        self.assertEqual(cfg.duration_seconds, 60.0)
        self.assertEqual(cfg.scope, "global")
        self.assertEqual(cfg.intensity, 0.9)
        self.assertEqual(cfg.target, "storage-service")
        self.assertEqual(cfg.parameters, {"fill_percent": 95})

    def test_invalid_duration(self) -> None:
        with self.assertRaises(ValueError):
            ExperimentConfig(
                experiment_type=ExperimentType.NETWORK_DELAY,
                duration_seconds=0,
            )

    def test_invalid_duration_negative(self) -> None:
        with self.assertRaises(ValueError):
            ExperimentConfig(
                experiment_type=ExperimentType.NETWORK_DELAY,
                duration_seconds=-5,
            )

    def test_invalid_intensity_too_high(self) -> None:
        with self.assertRaises(ValueError):
            ExperimentConfig(
                experiment_type=ExperimentType.CPU_SPIKE,
                intensity=1.5,
            )

    def test_invalid_intensity_negative(self) -> None:
        with self.assertRaises(ValueError):
            ExperimentConfig(
                experiment_type=ExperimentType.CPU_SPIKE,
                intensity=-0.1,
            )

    def test_config_is_frozen(self) -> None:
        cfg = ExperimentConfig(experiment_type=ExperimentType.NETWORK_DELAY)
        with self.assertRaises(AttributeError):
            cfg.duration_seconds = 99  # type: ignore[misc]


class TestExperimentResult(unittest.TestCase):
    def test_duration_property(self) -> None:
        result = ExperimentResult(
            experiment_id="abc123",
            experiment_type=ExperimentType.SERVICE_DOWN,
            status=ExperimentStatus.COMPLETED,
            started_at=100.0,
            ended_at=130.0,
            errors_observed=2,
        )
        self.assertAlmostEqual(result.duration_seconds, 30.0)
        self.assertEqual(result.errors_observed, 2)


class TestExperimentTypes(unittest.TestCase):
    def test_all_types(self) -> None:
        types = list(ExperimentType)
        self.assertEqual(len(types), 6)
        self.assertIn(ExperimentType.NETWORK_DELAY, types)
        self.assertIn(ExperimentType.DISK_FULL, types)
        self.assertIn(ExperimentType.SERVICE_DOWN, types)
        self.assertIn(ExperimentType.CPU_SPIKE, types)
        self.assertIn(ExperimentType.MEMORY_PRESSURE, types)
        self.assertIn(ExperimentType.CUSTOM, types)

    def test_all_statuses(self) -> None:
        statuses = list(ExperimentStatus)
        self.assertEqual(len(statuses), 5)


class TestChaosExperimentRunner(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = ChaosExperimentRunner()
        self.cfg = ExperimentConfig(
            experiment_type=ExperimentType.NETWORK_DELAY,
            duration_seconds=10.0,
        )

    def test_create_experiment(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        self.assertIsInstance(exp, Experiment)
        self.assertEqual(exp.status, ExperimentStatus.PENDING)
        self.assertEqual(exp.config, self.cfg)
        self.assertIsInstance(exp.id, str)
        self.assertEqual(len(exp.id), 12)

    def test_start_experiment(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        started = self.runner.start_experiment(exp.id)
        self.assertEqual(started.status, ExperimentStatus.RUNNING)
        self.assertGreater(started.started_at, 0)

    def test_start_nonexistent_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.runner.start_experiment("nonexistent")

    def test_start_already_running_raises(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        self.runner.start_experiment(exp.id)
        with self.assertRaises(RuntimeError):
            self.runner.start_experiment(exp.id)

    def test_complete_experiment(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        self.runner.start_experiment(exp.id)
        result = self.runner.complete_experiment(
            exp.id, errors_observed=3, recovery_time=5.0
        )
        self.assertIsInstance(result, ExperimentResult)
        self.assertEqual(result.status, ExperimentStatus.COMPLETED)
        self.assertEqual(result.errors_observed, 3)
        self.assertEqual(result.recovery_time_seconds, 5.0)

    def test_complete_nonexistent_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.runner.complete_experiment("nope")

    def test_complete_not_running_raises(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        with self.assertRaises(RuntimeError):
            self.runner.complete_experiment(exp.id)

    def test_abort_experiment(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        self.runner.start_experiment(exp.id)
        aborted = self.runner.abort_experiment(exp.id)
        self.assertEqual(aborted.status, ExperimentStatus.ABORTED)
        self.assertGreater(aborted.ended_at, 0)

    def test_abort_nonexistent_raises(self) -> None:
        with self.assertRaises(KeyError):
            self.runner.abort_experiment("nope")

    def test_abort_not_running_raises(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        with self.assertRaises(RuntimeError):
            self.runner.abort_experiment(exp.id)

    def test_get_experiment(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        fetched = self.runner.get_experiment(exp.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, exp.id)

    def test_get_nonexistent(self) -> None:
        self.assertIsNone(self.runner.get_experiment("nope"))

    def test_list_experiments(self) -> None:
        self.runner.create_experiment(self.cfg)
        cfg2 = ExperimentConfig(experiment_type=ExperimentType.DISK_FULL)
        self.runner.create_experiment(cfg2)
        exps = self.runner.list_experiments()
        self.assertEqual(len(exps), 2)

    def test_list_experiments_filter_status(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        self.runner.create_experiment(
            ExperimentConfig(experiment_type=ExperimentType.DISK_FULL)
        )
        self.runner.start_experiment(exp.id)
        running = self.runner.list_experiments(status=ExperimentStatus.RUNNING)
        self.assertEqual(len(running), 1)
        pending = self.runner.list_experiments(status=ExperimentStatus.PENDING)
        self.assertEqual(len(pending), 1)

    def test_history(self) -> None:
        exp = self.runner.create_experiment(self.cfg)
        self.runner.start_experiment(exp.id)
        self.runner.complete_experiment(exp.id)
        self.assertEqual(len(self.runner.history), 1)

    def test_history_is_copy(self) -> None:
        history = self.runner.history
        history.append(None)  # type: ignore[arg-type]
        self.assertEqual(len(self.runner.history), 0)


if __name__ == "__main__":
    unittest.main()
