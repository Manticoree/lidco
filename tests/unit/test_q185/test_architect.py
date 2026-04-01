"""Tests for feature_dev.architect — CodeArchitectAgent, data classes."""
from __future__ import annotations

import unittest

from lidco.feature_dev.architect import (
    ArchitectError,
    ArchitectureProposal,
    Blueprint,
    CodeArchitectAgent,
)


class TestArchitectureProposal(unittest.TestCase):
    def test_frozen(self):
        p = ArchitectureProposal(
            name="layered",
            description="Layered approach",
            trade_offs=("pro: clean",),
            complexity_score=0.5,
        )
        with self.assertRaises(AttributeError):
            p.name = "other"  # type: ignore[misc]

    def test_fields(self):
        p = ArchitectureProposal(
            name="modular",
            description="Modular approach",
            trade_offs=("pro: reusable", "con: overhead"),
            complexity_score=0.3,
        )
        self.assertEqual(p.name, "modular")
        self.assertEqual(p.description, "Modular approach")
        self.assertEqual(len(p.trade_offs), 2)
        self.assertAlmostEqual(p.complexity_score, 0.3)

    def test_equality(self):
        a = ArchitectureProposal("x", "y", ("a",), 0.5)
        b = ArchitectureProposal("x", "y", ("a",), 0.5)
        self.assertEqual(a, b)


class TestBlueprint(unittest.TestCase):
    def test_frozen(self):
        bp = Blueprint(
            components=("core",),
            dependencies=("typing",),
            files_to_create=("a.py",),
            files_to_modify=("b.py",),
            steps=("step1",),
        )
        with self.assertRaises(AttributeError):
            bp.components = ("other",)  # type: ignore[misc]

    def test_fields(self):
        bp = Blueprint(
            components=("core", "api"),
            dependencies=("typing", "dataclasses"),
            files_to_create=("src/x.py",),
            files_to_modify=("src/reg.py",),
            steps=("1. create", "2. wire"),
        )
        self.assertEqual(bp.components, ("core", "api"))
        self.assertEqual(len(bp.steps), 2)
        self.assertEqual(bp.files_to_create, ("src/x.py",))


class TestCodeArchitectPropose(unittest.TestCase):
    def test_empty_requirements_raises(self):
        agent = CodeArchitectAgent()
        with self.assertRaises(ArchitectError):
            agent.propose("")

    def test_whitespace_requirements_raises(self):
        agent = CodeArchitectAgent()
        with self.assertRaises(ArchitectError):
            agent.propose("   ")

    def test_returns_proposals(self):
        agent = CodeArchitectAgent()
        proposals = agent.propose("Add caching layer")
        self.assertIsInstance(proposals, tuple)
        self.assertGreaterEqual(len(proposals), 1)
        self.assertLessEqual(len(proposals), 3)

    def test_proposals_sorted_by_complexity(self):
        agent = CodeArchitectAgent()
        proposals = agent.propose("Add caching layer")
        scores = [p.complexity_score for p in proposals]
        self.assertEqual(scores, sorted(scores))

    def test_custom_patterns(self):
        agent = CodeArchitectAgent()
        proposals = agent.propose("feature", patterns=("plugin", "microservice"))
        self.assertEqual(len(proposals), 2)
        self.assertIn("plugin", proposals[0].name)

    def test_max_proposals_respected(self):
        agent = CodeArchitectAgent(max_proposals=1)
        proposals = agent.propose("feature")
        self.assertEqual(len(proposals), 1)

    def test_proposal_description_contains_requirements(self):
        agent = CodeArchitectAgent()
        proposals = agent.propose("Add authentication")
        self.assertTrue(any("authentication" in p.description.lower() for p in proposals))


class TestCodeArchitectRecommend(unittest.TestCase):
    def test_empty_proposals_raises(self):
        agent = CodeArchitectAgent()
        with self.assertRaises(ArchitectError):
            agent.recommend(())

    def test_returns_single_proposal(self):
        agent = CodeArchitectAgent()
        proposals = agent.propose("feature")
        best = agent.recommend(proposals)
        self.assertIsInstance(best, ArchitectureProposal)

    def test_prefers_mid_complexity(self):
        agent = CodeArchitectAgent()
        low = ArchitectureProposal("low", "d", (), 0.1)
        mid = ArchitectureProposal("mid", "d", (), 0.4)
        high = ArchitectureProposal("high", "d", (), 0.9)
        best = agent.recommend((low, mid, high))
        self.assertEqual(best.name, "mid")

    def test_single_proposal(self):
        agent = CodeArchitectAgent()
        p = ArchitectureProposal("only", "d", (), 0.5)
        best = agent.recommend((p,))
        self.assertEqual(best, p)


class TestCodeArchitectBlueprint(unittest.TestCase):
    def test_generates_blueprint(self):
        agent = CodeArchitectAgent()
        p = ArchitectureProposal("layered-approach", "desc", (), 0.5)
        bp = agent.generate_blueprint(p)
        self.assertIsInstance(bp, Blueprint)
        self.assertGreater(len(bp.components), 0)
        self.assertGreater(len(bp.files_to_create), 0)
        self.assertGreater(len(bp.steps), 0)

    def test_blueprint_has_dependencies(self):
        agent = CodeArchitectAgent()
        p = ArchitectureProposal("mod", "desc", (), 0.3)
        bp = agent.generate_blueprint(p)
        self.assertIn("typing", bp.dependencies)
        self.assertIn("dataclasses", bp.dependencies)

    def test_blueprint_components_contain_name(self):
        agent = CodeArchitectAgent()
        p = ArchitectureProposal("event-driven", "desc", (), 0.6)
        bp = agent.generate_blueprint(p)
        self.assertTrue(any("event_driven" in c for c in bp.components))

    def test_blueprint_steps_ordered(self):
        agent = CodeArchitectAgent()
        p = ArchitectureProposal("simple", "desc", (), 0.2)
        bp = agent.generate_blueprint(p)
        self.assertTrue(bp.steps[0].startswith("1."))


if __name__ == "__main__":
    unittest.main()
