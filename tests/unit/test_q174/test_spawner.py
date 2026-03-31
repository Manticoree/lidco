"""Tests for ExplorationSpawner."""
from __future__ import annotations

import unittest

from lidco.explore.spawner import (
    ExplorationConfig,
    ExplorationSpawner,
    ExplorationVariant,
)


class TestExplorationConfig(unittest.TestCase):
    def test_default_config(self) -> None:
        cfg = ExplorationConfig()
        self.assertEqual(cfg.max_variants, 3)
        self.assertEqual(cfg.strategies, ["conservative", "balanced", "aggressive"])
        self.assertEqual(cfg.timeout, 300.0)

    def test_custom_config(self) -> None:
        cfg = ExplorationConfig(max_variants=5, strategies=["a", "b"], timeout=60.0)
        self.assertEqual(cfg.max_variants, 5)
        self.assertEqual(cfg.strategies, ["a", "b"])
        self.assertEqual(cfg.timeout, 60.0)


class TestExplorationSpawner(unittest.TestCase):
    def setUp(self) -> None:
        self.spawner = ExplorationSpawner()

    def test_config_property(self) -> None:
        self.assertIsInstance(self.spawner.config, ExplorationConfig)

    def test_create_exploration(self) -> None:
        exp = self.spawner.create_exploration("fix the bug")
        self.assertTrue(exp.id.startswith("exp_"))
        self.assertEqual(exp.original_prompt, "fix the bug")
        self.assertEqual(len(exp.variants), 3)
        self.assertEqual(exp.status, "pending")

    def test_create_exploration_custom_variants(self) -> None:
        exp = self.spawner.create_exploration("task", num_variants=2)
        self.assertEqual(len(exp.variants), 2)

    def test_create_exploration_capped_at_max(self) -> None:
        exp = self.spawner.create_exploration("task", num_variants=100)
        self.assertEqual(len(exp.variants), 3)  # capped at max_variants=3

    def test_variant_strategies_applied(self) -> None:
        exp = self.spawner.create_exploration("do something")
        strategies = [v.strategy for v in exp.variants]
        self.assertEqual(strategies, ["conservative", "balanced", "aggressive"])

    def test_variant_prompt_prefixes(self) -> None:
        exp = self.spawner.create_exploration("do X")
        for v in exp.variants:
            self.assertIn("do X", v.prompt)
            self.assertTrue(len(v.prompt) > len("do X"))

    def test_variant_ids_unique(self) -> None:
        exp = self.spawner.create_exploration("task")
        ids = [v.id for v in exp.variants]
        self.assertEqual(len(ids), len(set(ids)))

    def test_variant_id_format(self) -> None:
        exp = self.spawner.create_exploration("task")
        for v in exp.variants:
            self.assertTrue(v.id.startswith("var_"))

    def test_exploration_id_format(self) -> None:
        exp = self.spawner.create_exploration("task")
        self.assertTrue(exp.id.startswith("exp_"))

    def test_start_variant(self) -> None:
        exp = self.spawner.create_exploration("task")
        vid = exp.variants[0].id
        updated = self.spawner.start_variant(exp.id, vid)
        started = [v for v in updated.variants if v.id == vid][0]
        self.assertEqual(started.status, "running")
        self.assertIsNotNone(started.started_at)
        self.assertEqual(updated.status, "running")

    def test_start_variant_not_found(self) -> None:
        with self.assertRaises(ValueError):
            self.spawner.start_variant("nonexistent", "v1")

    def test_complete_variant(self) -> None:
        exp = self.spawner.create_exploration("task")
        vid = exp.variants[0].id
        self.spawner.start_variant(exp.id, vid)
        updated = self.spawner.complete_variant(exp.id, vid, "done", "diff text")
        completed = [v for v in updated.variants if v.id == vid][0]
        self.assertEqual(completed.status, "completed")
        self.assertEqual(completed.result, "done")
        self.assertEqual(completed.diff, "diff text")
        self.assertIsNotNone(completed.completed_at)

    def test_complete_variant_all_done_marks_completed(self) -> None:
        cfg = ExplorationConfig(max_variants=1, strategies=["balanced"])
        spawner = ExplorationSpawner(cfg)
        exp = spawner.create_exploration("task")
        vid = exp.variants[0].id
        spawner.start_variant(exp.id, vid)
        updated = spawner.complete_variant(exp.id, vid, "result")
        self.assertEqual(updated.status, "completed")

    def test_complete_variant_not_found(self) -> None:
        with self.assertRaises(ValueError):
            self.spawner.complete_variant("nonexistent", "v1", "r")

    def test_fail_variant(self) -> None:
        exp = self.spawner.create_exploration("task")
        vid = exp.variants[0].id
        self.spawner.start_variant(exp.id, vid)
        updated = self.spawner.fail_variant(exp.id, vid, "oops")
        failed = [v for v in updated.variants if v.id == vid][0]
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error, "oops")

    def test_fail_variant_not_found(self) -> None:
        with self.assertRaises(ValueError):
            self.spawner.fail_variant("nonexistent", "v1", "err")

    def test_get_exploration(self) -> None:
        exp = self.spawner.create_exploration("task")
        found = self.spawner.get_exploration(exp.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, exp.id)

    def test_get_exploration_not_found(self) -> None:
        self.assertIsNone(self.spawner.get_exploration("missing"))

    def test_list_explorations_empty(self) -> None:
        self.assertEqual(self.spawner.list_explorations(), [])

    def test_list_explorations(self) -> None:
        self.spawner.create_exploration("a")
        self.spawner.create_exploration("b")
        self.assertEqual(len(self.spawner.list_explorations()), 2)

    def test_cancel_exploration(self) -> None:
        exp = self.spawner.create_exploration("task")
        cancelled = self.spawner.cancel_exploration(exp.id)
        self.assertEqual(cancelled.status, "cancelled")
        for v in cancelled.variants:
            self.assertEqual(v.status, "cancelled")

    def test_cancel_not_found(self) -> None:
        with self.assertRaises(ValueError):
            self.spawner.cancel_exploration("missing")

    def test_immutable_explorations(self) -> None:
        exp = self.spawner.create_exploration("task")
        vid = exp.variants[0].id
        self.spawner.start_variant(exp.id, vid)
        # Original object should still show pending
        self.assertEqual(exp.variants[0].status, "pending")

    def test_cancel_preserves_completed(self) -> None:
        cfg = ExplorationConfig(max_variants=2, strategies=["balanced", "aggressive"])
        spawner = ExplorationSpawner(cfg)
        exp = spawner.create_exploration("task")
        vid0 = exp.variants[0].id
        spawner.start_variant(exp.id, vid0)
        spawner.complete_variant(exp.id, vid0, "done")
        cancelled = spawner.cancel_exploration(exp.id)
        statuses = {v.id: v.status for v in cancelled.variants}
        self.assertEqual(statuses[vid0], "completed")
        self.assertEqual(statuses[exp.variants[1].id], "cancelled")


if __name__ == "__main__":
    unittest.main()
