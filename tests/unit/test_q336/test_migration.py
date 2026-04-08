"""Tests for lidco.archaeology.migration — MigrationAdvisor."""

from __future__ import annotations

import unittest

from lidco.archaeology.migration import (
    MigrationAdvisor,
    MigrationPlan,
    MigrationRisk,
    MigrationStep,
    RiskLevel,
)


class TestRiskLevel(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(RiskLevel.LOW.value, "low")
        self.assertEqual(RiskLevel.CRITICAL.value, "critical")


class TestMigrationRisk(unittest.TestCase):
    def test_is_blocking_high(self) -> None:
        r = MigrationRisk(description="d", level=RiskLevel.HIGH, mitigation="m")
        self.assertTrue(r.is_blocking())

    def test_is_blocking_critical(self) -> None:
        r = MigrationRisk(description="d", level=RiskLevel.CRITICAL, mitigation="m")
        self.assertTrue(r.is_blocking())

    def test_not_blocking_low(self) -> None:
        r = MigrationRisk(description="d", level=RiskLevel.LOW, mitigation="m")
        self.assertFalse(r.is_blocking())

    def test_not_blocking_medium(self) -> None:
        r = MigrationRisk(description="d", level=RiskLevel.MEDIUM, mitigation="m")
        self.assertFalse(r.is_blocking())

    def test_frozen(self) -> None:
        r = MigrationRisk(description="d", level=RiskLevel.LOW, mitigation="m")
        with self.assertRaises(AttributeError):
            r.description = "x"  # type: ignore[misc]


class TestMigrationStep(unittest.TestCase):
    def test_risk_count(self) -> None:
        risk = MigrationRisk(description="d", level=RiskLevel.LOW, mitigation="m")
        step = MigrationStep(order=1, title="t", description="d", risks=(risk,))
        self.assertEqual(step.risk_count, 1)

    def test_has_blocking_risks_true(self) -> None:
        risk = MigrationRisk(description="d", level=RiskLevel.HIGH, mitigation="m")
        step = MigrationStep(order=1, title="t", description="d", risks=(risk,))
        self.assertTrue(step.has_blocking_risks())

    def test_has_blocking_risks_false(self) -> None:
        step = MigrationStep(order=1, title="t", description="d")
        self.assertFalse(step.has_blocking_risks())


class TestMigrationPlan(unittest.TestCase):
    def test_step_count_empty(self) -> None:
        plan = MigrationPlan(name="test")
        self.assertEqual(plan.step_count, 0)

    def test_total_files(self) -> None:
        plan = MigrationPlan(
            name="test",
            steps=[
                MigrationStep(order=1, title="a", description="d", files=("x.py", "y.py")),
                MigrationStep(order=2, title="b", description="d", files=("y.py", "z.py")),
            ],
        )
        self.assertEqual(plan.total_files, 3)

    def test_blocking_count(self) -> None:
        risk = MigrationRisk(description="d", level=RiskLevel.CRITICAL, mitigation="m")
        plan = MigrationPlan(
            name="test",
            steps=[
                MigrationStep(order=1, title="a", description="d", risks=(risk,)),
                MigrationStep(order=2, title="b", description="d"),
            ],
        )
        self.assertEqual(plan.blocking_count, 1)

    def test_summary_contains_name(self) -> None:
        plan = MigrationPlan(name="my-migration")
        self.assertIn("my-migration", plan.summary())

    def test_summary_parallel_safe(self) -> None:
        plan = MigrationPlan(
            name="test",
            steps=[MigrationStep(order=1, title="a", description="d", parallel_safe=True)],
        )
        self.assertIn("parallel-safe", plan.summary())

    def test_summary_sequential(self) -> None:
        plan = MigrationPlan(
            name="test",
            steps=[MigrationStep(order=1, title="a", description="d", parallel_safe=False)],
        )
        self.assertIn("sequential", plan.summary())


class TestMigrationAdvisor(unittest.TestCase):
    def test_file_count_empty(self) -> None:
        advisor = MigrationAdvisor()
        self.assertEqual(advisor.file_count, 0)

    def test_add_file(self) -> None:
        advisor = MigrationAdvisor()
        advisor.add_file("a.py", "x = 1")
        self.assertEqual(advisor.file_count, 1)

    def test_assess_no_risks_small_file(self) -> None:
        advisor = MigrationAdvisor(files={"a.py": "x = 1\ny = 2"})
        risks = advisor.assess_risks()
        self.assertEqual(len(risks), 0)

    def test_assess_large_file_risk(self) -> None:
        big = "\n".join(f"line_{i} = {i}" for i in range(600))
        advisor = MigrationAdvisor(files={"big.py": big})
        risks = advisor.assess_risks()
        descs = [r.description for r in risks]
        self.assertTrue(any("Large file" in d for d in descs))

    def test_assess_global_state_risk(self) -> None:
        code = "def f():\n    global counter\n    counter += 1"
        advisor = MigrationAdvisor(files={"state.py": code})
        risks = advisor.assess_risks()
        self.assertTrue(any(r.level == RiskLevel.HIGH for r in risks))

    def test_assess_eval_risk(self) -> None:
        code = "result = eval(user_input)"
        advisor = MigrationAdvisor(files={"danger.py": code})
        risks = advisor.assess_risks()
        self.assertTrue(any(r.level == RiskLevel.CRITICAL for r in risks))

    def test_plan_empty(self) -> None:
        advisor = MigrationAdvisor()
        plan = advisor.plan("empty")
        self.assertEqual(plan.name, "empty")
        # At minimum: characterisation tests + cleanup
        self.assertGreaterEqual(plan.step_count, 2)

    def test_plan_with_critical_files(self) -> None:
        code = "result = eval(data)"
        advisor = MigrationAdvisor(files={"bad.py": code})
        plan = advisor.plan("critical-test")
        self.assertEqual(plan.overall_risk, RiskLevel.CRITICAL)
        self.assertTrue(plan.blocking_count > 0)

    def test_plan_with_normal_files(self) -> None:
        advisor = MigrationAdvisor(files={"ok.py": "x = 1"})
        plan = advisor.plan()
        self.assertEqual(plan.overall_risk, RiskLevel.LOW)

    def test_plan_step_order(self) -> None:
        code = "result = eval(data)"
        advisor = MigrationAdvisor(files={"bad.py": code, "ok.py": "x = 1"})
        plan = advisor.plan()
        orders = [s.order for s in plan.steps]
        self.assertEqual(orders, sorted(orders))

    def test_plan_first_step_is_tests(self) -> None:
        advisor = MigrationAdvisor(files={"a.py": "x = 1"})
        plan = advisor.plan()
        self.assertIn("test", plan.steps[0].title.lower())

    def test_plan_last_step_is_cleanup(self) -> None:
        advisor = MigrationAdvisor(files={"a.py": "x = 1"})
        plan = advisor.plan()
        self.assertIn("remove", plan.steps[-1].title.lower())


if __name__ == "__main__":
    unittest.main()
