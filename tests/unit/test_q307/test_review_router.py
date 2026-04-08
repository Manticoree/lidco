"""Tests for ReviewRouter."""

import unittest

from lidco.ownership.review_router import (
    EscalationResult,
    ReviewAssignment,
    Reviewer,
    ReviewRouter,
    RoutingResult,
)


class TestDataclasses(unittest.TestCase):
    def test_reviewer_defaults(self):
        r = Reviewer(name="alice", team="backend")
        self.assertTrue(r.is_available)
        self.assertEqual(r.current_load, 0)

    def test_review_assignment_frozen(self):
        a = ReviewAssignment(file_pattern="src/*", reviewers=["alice"], reason="match")
        with self.assertRaises(AttributeError):
            a.reason = "other"  # type: ignore[misc]

    def test_escalation_result_frozen(self):
        e = EscalationResult(original_reviewer="alice", escalated_to="bob", reason="vacation")
        self.assertEqual(e.reason, "vacation")

    def test_routing_result_summary(self):
        r = RoutingResult(
            assignments=[ReviewAssignment("a", ["x"], "r")],
            escalations=[],
            unassigned=["b"],
        )
        s = r.summary()
        self.assertEqual(s["assigned_count"], 1)
        self.assertEqual(s["unassigned_count"], 1)
        self.assertEqual(s["escalation_count"], 0)


class TestReviewRouter(unittest.TestCase):
    def _make_router(self) -> ReviewRouter:
        router = ReviewRouter()
        router = router.add_reviewer(Reviewer(name="alice", team="backend"))
        router = router.add_reviewer(Reviewer(name="bob", team="backend"))
        router = router.add_reviewer(Reviewer(name="carol", team="frontend"))
        router = router.set_ownership("src/*", ["alice", "bob"])
        router = router.set_ownership("web/*", ["carol"])
        return router

    def test_add_reviewer_immutable(self):
        r1 = ReviewRouter()
        r2 = r1.add_reviewer(Reviewer(name="alice", team="backend"))
        self.assertIsNot(r1, r2)
        self.assertEqual(len(r1._reviewers), 0)
        self.assertEqual(len(r2._reviewers), 1)

    def test_set_ownership_immutable(self):
        r1 = ReviewRouter()
        r2 = r1.set_ownership("src/*", ["alice"])
        self.assertIsNot(r1, r2)
        self.assertEqual(len(r1._ownership_map), 0)

    def test_set_vacation_immutable(self):
        r1 = ReviewRouter()
        r2 = r1.set_vacation("alice")
        self.assertIsNot(r1, r2)
        self.assertNotIn("alice", r1._vacation_set)
        self.assertIn("alice", r2._vacation_set)

    def test_set_escalation_immutable(self):
        r1 = ReviewRouter()
        r2 = r1.set_escalation("alice", "bob")
        self.assertIsNot(r1, r2)
        self.assertNotIn("alice", r1._escalation_map)
        self.assertEqual(r2._escalation_map["alice"], "bob")

    def test_route_basic(self):
        router = self._make_router()
        result = router.route(["src/main.py", "src/util.py"])
        self.assertGreater(len(result.assignments), 0)
        for a in result.assignments:
            self.assertIn("alice", a.reviewers)

    def test_route_unmatched_files(self):
        router = self._make_router()
        result = router.route(["unknown/file.py"])
        self.assertEqual(len(result.assignments), 0)
        self.assertIn("unknown/file.py", result.unassigned)

    def test_route_with_vacation_escalation(self):
        router = self._make_router()
        router = router.set_vacation("alice")
        router = router.set_escalation("alice", "bob")
        result = router.route(["src/main.py"])
        # Should have an escalation
        self.assertGreater(len(result.escalations), 0)
        self.assertEqual(result.escalations[0].original_reviewer, "alice")
        self.assertEqual(result.escalations[0].escalated_to, "bob")

    def test_route_vacation_no_escalation(self):
        router = ReviewRouter()
        router = router.add_reviewer(Reviewer(name="alice", team="t"))
        router = router.set_ownership("src/*", ["alice"])
        router = router.set_vacation("alice")
        result = router.route(["src/a.py"])
        # No escalation target: file should be unassigned
        self.assertIn("src/a.py", result.unassigned)

    def test_round_robin(self):
        router = self._make_router()
        first = router.route_round_robin("backend", 1)
        self.assertEqual(len(first), 1)
        self.assertIn(first[0], ["alice", "bob"])

    def test_round_robin_empty_team(self):
        router = ReviewRouter()
        result = router.route_round_robin("nonexistent", 1)
        self.assertEqual(result, [])

    def test_round_robin_skips_vacation(self):
        router = self._make_router()
        router = router.set_vacation("alice")
        picked = router.route_round_robin("backend", 1)
        self.assertEqual(picked, ["bob"])

    def test_find_least_loaded(self):
        router = ReviewRouter()
        router = router.add_reviewer(Reviewer("alice", "t", True, current_load=5))
        router = router.add_reviewer(Reviewer("bob", "t", True, current_load=2))
        result = router.find_least_loaded("t")
        self.assertEqual(result, "bob")

    def test_find_least_loaded_empty(self):
        router = ReviewRouter()
        self.assertIsNone(router.find_least_loaded("nonexistent"))

    def test_find_least_loaded_skip_vacation(self):
        router = ReviewRouter()
        router = router.add_reviewer(Reviewer("alice", "t", True, current_load=1))
        router = router.add_reviewer(Reviewer("bob", "t", True, current_load=5))
        router = router.set_vacation("alice")
        result = router.find_least_loaded("t")
        self.assertEqual(result, "bob")

    def test_pattern_matches_wildcard(self):
        self.assertTrue(ReviewRouter._pattern_matches("*", "anything.py"))

    def test_pattern_matches_prefix(self):
        self.assertTrue(ReviewRouter._pattern_matches("src/*", "src/main.py"))
        self.assertFalse(ReviewRouter._pattern_matches("src/*", "lib/x.py"))

    def test_pattern_matches_exact(self):
        self.assertTrue(ReviewRouter._pattern_matches("src/main.py", "src/main.py"))


if __name__ == "__main__":
    unittest.main()
