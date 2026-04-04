"""Tests for metacog.boundary."""
import unittest
from lidco.metacog.boundary import KnowledgeBoundary, BoundaryAssessment


class TestKnowledgeBoundary(unittest.TestCase):

    def setUp(self):
        self.kb = KnowledgeBoundary()

    def test_known_domain(self):
        self.kb.add_known_domain("python")
        a = self.kb.assess("How do Python decorators work?")
        self.assertEqual(a.category, "known")
        self.assertTrue(a.within_boundary)

    def test_uncertain_pattern(self):
        self.kb.add_uncertain_pattern("quantum")
        a = self.kb.assess("Explain quantum computing algorithms")
        self.assertEqual(a.category, "uncertain")
        self.assertFalse(a.within_boundary)

    def test_unknown_query(self):
        a = self.kb.assess("Something completely unrecognized")
        self.assertEqual(a.category, "unknown")
        self.assertFalse(a.within_boundary)

    def test_time_sensitive_reduces_confidence(self):
        self.kb.add_known_domain("python")
        a1 = self.kb.assess("How do Python decorators work?")
        a2 = self.kb.assess("What is the latest Python version?")
        self.assertLess(a2.confidence, a1.confidence)

    def test_verification_steps_for_uncertain(self):
        self.kb.add_uncertain_pattern("blockchain")
        a = self.kb.assess("Blockchain consensus mechanisms")
        self.assertGreater(len(a.verification_steps), 0)

    def test_history(self):
        self.kb.assess("Query 1")
        self.kb.assess("Query 2")
        self.assertEqual(len(self.kb.history()), 2)

    def test_uncertain_ratio(self):
        self.kb.add_known_domain("python")
        self.kb.assess("Python lists")
        self.kb.assess("Unknown topic")
        ratio = self.kb.uncertain_ratio()
        self.assertEqual(ratio, 0.5)

    def test_uncertain_ratio_empty(self):
        self.assertEqual(self.kb.uncertain_ratio(), 0.0)

    def test_summary(self):
        self.kb.add_known_domain("python")
        s = self.kb.summary()
        self.assertEqual(s["known_domains"], 1)

    def test_suggested_sources(self):
        a = self.kb.assess("Random query")
        self.assertIsInstance(a.suggested_sources, list)


if __name__ == "__main__":
    unittest.main()
