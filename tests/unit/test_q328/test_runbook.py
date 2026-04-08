"""Tests for lidco.sre.runbook — Runbook Generator."""
from __future__ import annotations

import unittest

from lidco.sre.runbook import (
    CheckResult,
    DecisionNode,
    Runbook,
    RunbookError,
    RunbookGenerator,
    RunbookStep,
    StepType,
)


class TestRunbookDataclasses(unittest.TestCase):
    def test_runbook_step_defaults(self) -> None:
        step = RunbookStep(title="Check logs")
        self.assertEqual(step.step_type, StepType.MANUAL)
        self.assertEqual(step.timeout_seconds, 300.0)

    def test_decision_node(self) -> None:
        node = DecisionNode(question="Is DB up?", yes_step="s1", no_step="s2")
        self.assertEqual(node.question, "Is DB up?")

    def test_check_result(self) -> None:
        cr = CheckResult(step_id="s1", passed=True, output="ok")
        self.assertTrue(cr.passed)

    def test_runbook_defaults(self) -> None:
        rb = Runbook(name="deploy")
        self.assertEqual(rb.version, "1.0.0")
        self.assertEqual(rb.step_count(), 0)

    def test_runbook_step_count(self) -> None:
        rb = Runbook(name="x", steps=[RunbookStep(title="a"), RunbookStep(title="b")])
        self.assertEqual(rb.step_count(), 2)

    def test_runbook_automated_steps(self) -> None:
        rb = Runbook(name="x", steps=[
            RunbookStep(title="manual", step_type=StepType.MANUAL),
            RunbookStep(title="auto", step_type=StepType.AUTOMATED),
            RunbookStep(title="check", step_type=StepType.CHECK),
        ])
        self.assertEqual(len(rb.automated_steps()), 2)

    def test_runbook_render_markdown(self) -> None:
        rb = Runbook(name="Deploy", version="2.0", author="bob", description="Deploy steps")
        rb.steps = [
            RunbookStep(title="Pull code", step_type=StepType.MANUAL, description="git pull"),
            RunbookStep(title="Run tests", step_type=StepType.AUTOMATED, command="pytest"),
        ]
        rb.decisions = [DecisionNode(question="Tests pass?", yes_step="deploy", no_step="rollback")]
        md = rb.render_markdown()
        self.assertIn("# Deploy", md)
        self.assertIn("**Version:** 2.0", md)
        self.assertIn("[manual]", md)
        self.assertIn("[automated]", md)
        self.assertIn("pytest", md)
        self.assertIn("Tests pass?", md)

    def test_step_type_values(self) -> None:
        self.assertEqual(StepType.MANUAL.value, "manual")
        self.assertEqual(StepType.DECISION.value, "decision")


class TestRunbookGenerator(unittest.TestCase):
    def setUp(self) -> None:
        self.gen = RunbookGenerator()

    def test_create(self) -> None:
        rb = self.gen.create("deploy", author="alice")
        self.assertEqual(rb.name, "deploy")
        self.assertEqual(rb.author, "alice")

    def test_create_no_name_raises(self) -> None:
        with self.assertRaises(RunbookError):
            self.gen.create("")

    def test_get(self) -> None:
        rb = self.gen.create("x")
        result = self.gen.get(rb.id)
        self.assertEqual(result.name, "x")

    def test_get_not_found(self) -> None:
        with self.assertRaises(RunbookError):
            self.gen.get("bad")

    def test_list_runbooks(self) -> None:
        self.gen.create("a")
        self.gen.create("b")
        self.assertEqual(len(self.gen.list_runbooks()), 2)

    def test_remove(self) -> None:
        rb = self.gen.create("rm")
        self.gen.remove(rb.id)
        self.assertEqual(len(self.gen.list_runbooks()), 0)

    def test_remove_not_found(self) -> None:
        with self.assertRaises(RunbookError):
            self.gen.remove("nope")

    def test_add_step(self) -> None:
        rb = self.gen.create("x")
        step = self.gen.add_step(rb.id, RunbookStep(title="step1"))
        self.assertEqual(rb.step_count(), 1)
        self.assertEqual(step.title, "step1")

    def test_add_decision(self) -> None:
        rb = self.gen.create("x")
        dec = self.gen.add_decision(rb.id, DecisionNode(question="ok?"))
        self.assertEqual(len(rb.decisions), 1)

    def test_register_and_run_check(self) -> None:
        rb = self.gen.create("x")
        step = self.gen.add_step(rb.id, RunbookStep(title="check", step_type=StepType.CHECK))
        self.gen.register_check(step.id, lambda: CheckResult(step_id=step.id, passed=True, output="ok"))
        result = self.gen.run_check(step.id)
        self.assertTrue(result.passed)

    def test_run_check_not_found(self) -> None:
        with self.assertRaises(RunbookError):
            self.gen.run_check("nope")

    def test_run_all_checks(self) -> None:
        rb = self.gen.create("x")
        s1 = self.gen.add_step(rb.id, RunbookStep(title="c1", step_type=StepType.CHECK))
        s2 = self.gen.add_step(rb.id, RunbookStep(title="c2", step_type=StepType.AUTOMATED))
        self.gen.register_check(s1.id, lambda: CheckResult(step_id=s1.id, passed=True))
        self.gen.register_check(s2.id, lambda: CheckResult(step_id=s2.id, passed=False))
        results = self.gen.run_all_checks(rb.id)
        self.assertEqual(len(results), 2)

    def test_new_version(self) -> None:
        rb = self.gen.create("x")
        self.gen.add_step(rb.id, RunbookStep(title="step"))
        new_rb = self.gen.new_version(rb.id, "2.0.0")
        self.assertEqual(new_rb.version, "2.0.0")
        self.assertEqual(new_rb.step_count(), 1)
        self.assertNotEqual(new_rb.id, rb.id)

    def test_from_procedure(self) -> None:
        lines = [
            "[auto] Run health check",
            "Verify logs",
            "[check] Disk space",
            "[decision] Is service healthy?",
            "",  # empty line should be skipped
        ]
        rb = self.gen.from_procedure("deploy", lines, author="bob")
        self.assertEqual(rb.name, "deploy")
        self.assertEqual(rb.step_count(), 4)
        self.assertEqual(rb.steps[0].step_type, StepType.AUTOMATED)
        self.assertEqual(rb.steps[1].step_type, StepType.MANUAL)
        self.assertEqual(rb.steps[2].step_type, StepType.CHECK)
        self.assertEqual(rb.steps[3].step_type, StepType.DECISION)

    def test_from_procedure_automated_tag(self) -> None:
        lines = ["[automated] Full scan"]
        rb = self.gen.from_procedure("scan", lines)
        self.assertEqual(rb.steps[0].step_type, StepType.AUTOMATED)
        self.assertIn("Full scan", rb.steps[0].title)


if __name__ == "__main__":
    unittest.main()
