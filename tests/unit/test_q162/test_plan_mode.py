"""Tests for lidco.modes.plan_mode — Q162 Task 923."""
from __future__ import annotations

import unittest

from lidco.modes.plan_mode import PlanMode, PlanModeState


class TestPlanModeState(unittest.TestCase):
    def test_defaults(self) -> None:
        s = PlanModeState()
        self.assertFalse(s.active)
        self.assertIsInstance(s.blocked_operations, list)
        self.assertIn("file_write", s.blocked_operations)
        self.assertEqual(s.plan_output, [])


class TestPlanMode(unittest.TestCase):
    def test_initially_inactive(self) -> None:
        pm = PlanMode()
        self.assertFalse(pm.is_active)

    def test_activate_deactivate(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertTrue(pm.is_active)
        pm.deactivate()
        self.assertFalse(pm.is_active)

    # -- check_operation when inactive --

    def test_inactive_allows_everything(self) -> None:
        pm = PlanMode()
        for op in ["file_write", "file_delete", "bash_execute", "git_push", "git_commit", "file_read"]:
            self.assertTrue(pm.check_operation(op))

    # -- check_operation when active --

    def test_active_blocks_write(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertFalse(pm.check_operation("file_write"))

    def test_active_blocks_delete(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertFalse(pm.check_operation("file_delete"))

    def test_active_blocks_bash_execute(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertFalse(pm.check_operation("bash_execute"))

    def test_active_blocks_git_push(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertFalse(pm.check_operation("git_push"))

    def test_active_blocks_git_commit(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertFalse(pm.check_operation("git_commit"))

    def test_active_allows_file_read(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertTrue(pm.check_operation("file_read"))

    def test_active_allows_grep(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertTrue(pm.check_operation("grep"))

    def test_active_allows_glob(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertTrue(pm.check_operation("glob"))

    def test_active_allows_git_status(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertTrue(pm.check_operation("git_status"))

    def test_active_allows_git_diff(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertTrue(pm.check_operation("git_diff"))

    def test_active_allows_git_log(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertTrue(pm.check_operation("git_log"))

    def test_active_blocks_unknown_op(self) -> None:
        pm = PlanMode()
        pm.activate()
        self.assertFalse(pm.check_operation("something_random"))

    # -- plan accumulation --

    def test_add_plan_line(self) -> None:
        pm = PlanMode()
        pm.add_plan_line("Step 1: read files")
        pm.add_plan_line("Step 2: analyze")
        self.assertEqual(pm.get_plan(), "Step 1: read files\nStep 2: analyze")

    def test_get_plan_empty(self) -> None:
        pm = PlanMode()
        self.assertEqual(pm.get_plan(), "")

    def test_clear(self) -> None:
        pm = PlanMode()
        pm.add_plan_line("something")
        pm.clear()
        self.assertEqual(pm.get_plan(), "")

    def test_state_snapshot(self) -> None:
        pm = PlanMode()
        pm.activate()
        pm.add_plan_line("line1")
        state = pm.state()
        self.assertIsInstance(state, PlanModeState)
        self.assertTrue(state.active)
        self.assertEqual(state.plan_output, ["line1"])
        self.assertIn("file_write", state.blocked_operations)


if __name__ == "__main__":
    unittest.main()
