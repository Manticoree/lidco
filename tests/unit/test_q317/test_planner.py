"""Tests for lidco.e2e_intel.planner — E2ETestPlanner."""

from __future__ import annotations

import unittest

from lidco.e2e_intel.planner import (
    CriticalPath,
    E2ETestPlanner,
    Priority,
    TestPlan,
    TestPlanEntry,
    UserJourney,
    UserStep,
)


class TestPriorityEnum(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(Priority.CRITICAL.value, "critical")
        self.assertEqual(Priority.HIGH.value, "high")
        self.assertEqual(Priority.MEDIUM.value, "medium")
        self.assertEqual(Priority.LOW.value, "low")


class TestUserStep(unittest.TestCase):
    def test_frozen(self) -> None:
        s = UserStep(action="click", target="btn")
        with self.assertRaises(AttributeError):
            s.action = "fill"  # type: ignore[misc]

    def test_fields(self) -> None:
        s = UserStep(action="fill", target="input", description="type email")
        self.assertEqual(s.action, "fill")
        self.assertEqual(s.target, "input")
        self.assertEqual(s.description, "type email")


class TestUserJourney(unittest.TestCase):
    def test_frozen(self) -> None:
        j = UserJourney(name="login", steps=())
        with self.assertRaises(AttributeError):
            j.name = "x"  # type: ignore[misc]

    def test_id_is_stable(self) -> None:
        j = UserJourney(name="login", steps=(UserStep("a", "b"),))
        self.assertEqual(j.id, j.id)
        self.assertEqual(len(j.id), 12)

    def test_default_priority(self) -> None:
        j = UserJourney(name="x", steps=())
        self.assertEqual(j.priority, Priority.MEDIUM)


class TestCriticalPath(unittest.TestCase):
    def test_frozen(self) -> None:
        cp = CriticalPath(name="cp", journeys=(), risk_score=0.5)
        with self.assertRaises(AttributeError):
            cp.risk_score = 0.9  # type: ignore[misc]


class TestTestPlanEntry(unittest.TestCase):
    def test_frozen(self) -> None:
        e = TestPlanEntry(
            journey_name="j", priority=Priority.HIGH, estimated_duration_s=10.0
        )
        with self.assertRaises(AttributeError):
            e.journey_name = "x"  # type: ignore[misc]

    def test_default_dependencies(self) -> None:
        e = TestPlanEntry(
            journey_name="j", priority=Priority.LOW, estimated_duration_s=1.0
        )
        self.assertEqual(e.dependencies, ())


class TestE2ETestPlanner(unittest.TestCase):
    def _step(self, target: str = "page") -> UserStep:
        return UserStep(action="click", target=target)

    def _journey(
        self,
        name: str = "j1",
        targets: tuple[str, ...] = ("page",),
        priority: Priority = Priority.MEDIUM,
    ) -> UserJourney:
        return UserJourney(
            name=name,
            steps=tuple(self._step(t) for t in targets),
            priority=priority,
        )

    def test_empty_plan(self) -> None:
        planner = E2ETestPlanner()
        plan = planner.plan()
        self.assertEqual(plan.entries, ())
        self.assertEqual(plan.total_estimated_duration_s, 0.0)
        self.assertEqual(plan.critical_paths, ())
        self.assertEqual(plan.coverage_score, 0.0)

    def test_add_journey_returns_new_planner(self) -> None:
        p1 = E2ETestPlanner()
        p2 = p1.add_journey(self._journey("a"))
        self.assertEqual(len(p1.journeys), 0)
        self.assertEqual(len(p2.journeys), 1)

    def test_add_journeys_returns_new_planner(self) -> None:
        p1 = E2ETestPlanner()
        p2 = p1.add_journeys([self._journey("a"), self._journey("b")])
        self.assertEqual(len(p1.journeys), 0)
        self.assertEqual(len(p2.journeys), 2)

    def test_plan_single_journey(self) -> None:
        planner = E2ETestPlanner(default_step_duration_s=3.0)
        planner = planner.add_journey(
            self._journey("login", ("page", "btn"))
        )
        plan = planner.plan()
        self.assertEqual(len(plan.entries), 1)
        self.assertEqual(plan.entries[0].journey_name, "login")
        self.assertAlmostEqual(plan.entries[0].estimated_duration_s, 6.0)

    def test_plan_priority_ordering(self) -> None:
        planner = E2ETestPlanner()
        planner = planner.add_journeys([
            self._journey("low", priority=Priority.LOW),
            self._journey("crit", priority=Priority.CRITICAL),
            self._journey("high", priority=Priority.HIGH),
        ])
        plan = planner.plan()
        names = [e.journey_name for e in plan.entries]
        self.assertEqual(names, ["crit", "high", "low"])

    def test_critical_paths_identified(self) -> None:
        # 3 journeys sharing the same target "checkout" — risk >= 0.7
        planner = E2ETestPlanner(critical_risk_threshold=0.5)
        planner = planner.add_journeys([
            self._journey("a", ("checkout",)),
            self._journey("b", ("checkout",)),
            self._journey("c", ("checkout",)),
        ])
        paths = planner.identify_critical_paths()
        self.assertGreater(len(paths), 0)
        self.assertEqual(paths[0].name, "shared:checkout")
        self.assertGreaterEqual(paths[0].risk_score, 0.5)

    def test_no_critical_paths_below_threshold(self) -> None:
        planner = E2ETestPlanner(critical_risk_threshold=0.9)
        planner = planner.add_journeys([
            self._journey("a", ("x",)),
            self._journey("b", ("y",)),
            self._journey("c", ("z",)),
        ])
        paths = planner.identify_critical_paths()
        self.assertEqual(len(paths), 0)

    def test_plan_total_duration(self) -> None:
        planner = E2ETestPlanner(default_step_duration_s=2.0)
        planner = planner.add_journeys([
            self._journey("a", ("p1", "p2")),  # 4s
            self._journey("b", ("p1",)),  # 2s
        ])
        plan = planner.plan()
        self.assertAlmostEqual(plan.total_estimated_duration_s, 6.0)

    def test_plan_coverage_score(self) -> None:
        planner = E2ETestPlanner()
        planner = planner.add_journey(self._journey("a"))
        plan = planner.plan()
        self.assertAlmostEqual(plan.coverage_score, 1.0)

    def test_dependencies_detected(self) -> None:
        planner = E2ETestPlanner()
        planner = planner.add_journeys([
            self._journey("a", ("shared_page",)),
            self._journey("b", ("shared_page",)),
        ])
        plan = planner.plan()
        # Both should list the other as dependency
        deps_a = plan.entries[0].dependencies
        deps_b = plan.entries[1].dependencies
        self.assertIn("b", deps_a)
        self.assertIn("a", deps_b)


if __name__ == "__main__":
    unittest.main()
