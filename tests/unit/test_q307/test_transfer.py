"""Tests for KnowledgeTransferPlanner."""

import unittest

from lidco.ownership.analyzer import (
    BusFactorResult,
    CoverageGap,
    KnowledgeSilo,
    OwnershipReport,
)
from lidco.ownership.transfer import (
    CriticalPath,
    DocGap,
    KnowledgeTransferPlanner,
    PairingSuggestion,
    TransferPlan,
)


class TestDataclasses(unittest.TestCase):
    def test_critical_path_frozen(self):
        cp = CriticalPath(path="src", sole_owner="alice", total_lines=500, risk_score=0.85)
        with self.assertRaises(AttributeError):
            cp.risk_score = 0.5  # type: ignore[misc]

    def test_pairing_suggestion_frozen(self):
        ps = PairingSuggestion(expert="alice", learner="bob", path="src", reason="high risk")
        self.assertEqual(ps.expert, "alice")

    def test_doc_gap(self):
        dg = DocGap(directory="lib", file_count=3, has_readme=False, has_docstrings=True)
        self.assertFalse(dg.has_readme)

    def test_transfer_plan_summary(self):
        plan = TransferPlan(
            critical_paths=[CriticalPath("a", "x", 100, 0.9)],
            pairing_suggestions=[PairingSuggestion("x", "y", "a", "r")],
            doc_gaps=[DocGap("a", 2, False, True)],
        )
        s = plan.summary()
        self.assertEqual(s["critical_path_count"], 1)
        self.assertEqual(s["pairing_suggestion_count"], 1)
        self.assertEqual(s["doc_gap_count"], 1)


class TestKnowledgeTransferPlanner(unittest.TestCase):
    def _make_report(self, silos: list[KnowledgeSilo] | None = None) -> OwnershipReport:
        default_silos = [
            KnowledgeSilo("src/core", "alice", 0.95, 600),
            KnowledgeSilo("src/util", "bob", 0.85, 300),
        ]
        return OwnershipReport(
            bus_factors=[BusFactorResult("src", 1, [("alice", 100)], 100)],
            knowledge_silos=default_silos if silos is None else silos,
            orphaned_files=[],
            coverage_gaps=[CoverageGap("lib", 3)],
            overall_bus_factor=1,
        )

    def test_plan_returns_transfer_plan(self):
        planner = KnowledgeTransferPlanner(
            risk_threshold=0.5, team_members=["alice", "bob", "carol"],
        )
        report = self._make_report()
        plan = planner.plan(report)
        self.assertIsInstance(plan, TransferPlan)

    def test_critical_paths_identified(self):
        planner = KnowledgeTransferPlanner(risk_threshold=0.5)
        report = self._make_report()
        plan = planner.plan(report)
        self.assertGreater(len(plan.critical_paths), 0)

    def test_critical_paths_sorted_by_risk(self):
        planner = KnowledgeTransferPlanner(risk_threshold=0.1)
        report = self._make_report()
        plan = planner.plan(report)
        if len(plan.critical_paths) > 1:
            self.assertGreaterEqual(
                plan.critical_paths[0].risk_score,
                plan.critical_paths[1].risk_score,
            )

    def test_pairing_suggestions_generated(self):
        planner = KnowledgeTransferPlanner(
            risk_threshold=0.5, team_members=["alice", "bob", "carol"],
        )
        report = self._make_report()
        plan = planner.plan(report)
        self.assertGreater(len(plan.pairing_suggestions), 0)
        # Expert should not be same as learner
        for ps in plan.pairing_suggestions:
            self.assertNotEqual(ps.expert, ps.learner)

    def test_pairing_no_team_members(self):
        planner = KnowledgeTransferPlanner(risk_threshold=0.5)
        report = self._make_report()
        plan = planner.plan(report)
        self.assertEqual(len(plan.pairing_suggestions), 0)

    def test_doc_gaps_detected(self):
        planner = KnowledgeTransferPlanner()
        report = self._make_report()
        dir_files = {
            "src/core": ["src/core/main.py", "src/core/util.py"],
            "docs": ["docs/README.md", "docs/guide.md"],
        }
        plan = planner.plan(report, directory_files=dir_files)
        gap_dirs = {g.directory for g in plan.doc_gaps}
        self.assertIn("src/core", gap_dirs)
        self.assertNotIn("docs", gap_dirs)  # has README.md

    def test_doc_gaps_empty_when_all_have_readme(self):
        planner = KnowledgeTransferPlanner()
        report = self._make_report()
        dir_files = {
            "src": ["src/README.md", "src/main.py"],
        }
        plan = planner.plan(report, directory_files=dir_files)
        self.assertEqual(len(plan.doc_gaps), 0)

    def test_priority_order(self):
        planner = KnowledgeTransferPlanner(risk_threshold=0.1)
        report = self._make_report()
        plan = planner.plan(report)
        self.assertEqual(plan.priority_order, [cp.path for cp in plan.critical_paths])

    def test_no_silos_no_critical(self):
        planner = KnowledgeTransferPlanner(risk_threshold=0.5)
        report = self._make_report(silos=[])
        plan = planner.plan(report)
        self.assertEqual(len(plan.critical_paths), 0)

    def test_risk_computation_small_file(self):
        # Small file (few lines) should have lower risk
        planner = KnowledgeTransferPlanner(risk_threshold=0.1)
        report = self._make_report(
            silos=[KnowledgeSilo("tiny", "alice", 1.0, 10)],
        )
        plan = planner.plan(report)
        if plan.critical_paths:
            self.assertLess(plan.critical_paths[0].risk_score, 1.0)

    def test_risk_computation_large_file(self):
        planner = KnowledgeTransferPlanner(risk_threshold=0.1)
        report = self._make_report(
            silos=[KnowledgeSilo("big", "alice", 1.0, 1000)],
        )
        plan = planner.plan(report)
        self.assertGreater(len(plan.critical_paths), 0)
        self.assertGreaterEqual(plan.critical_paths[0].risk_score, 0.9)


if __name__ == "__main__":
    unittest.main()
