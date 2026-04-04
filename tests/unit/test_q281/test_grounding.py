"""Tests for hallucination.grounding."""
import unittest
from lidco.hallucination.grounding import GroundingEngine, Citation


class TestGroundingEngine(unittest.TestCase):

    def setUp(self):
        self.ge = GroundingEngine()

    def test_add_source(self):
        self.ge.add_source("doc1", "Python is a programming language")
        self.assertIn("doc1", self.ge.sources())

    def test_remove_source(self):
        self.ge.add_source("doc1", "Content")
        self.assertTrue(self.ge.remove_source("doc1"))
        self.assertNotIn("doc1", self.ge.sources())

    def test_remove_nonexistent(self):
        self.assertFalse(self.ge.remove_source("nope"))

    def test_ground_claim_found(self):
        self.ge.add_source("doc1", "Python supports decorators and generators")
        citation = self.ge.ground_claim("Python decorators are powerful")
        self.assertIsNotNone(citation)
        self.assertEqual(citation.source, "doc1")

    def test_ground_claim_not_found(self):
        self.ge.add_source("doc1", "JavaScript is event-driven")
        citation = self.ge.ground_claim("Rust memory safety")
        self.assertIsNone(citation)

    def test_ground_multiple(self):
        self.ge.add_source("doc1", "The system uses Python and Flask for the backend")
        result = self.ge.ground([
            "The system uses Python",
            "The system uses completely unknown alien technology",
        ])
        self.assertEqual(result.total_claims, 2)
        self.assertGreater(result.grounded_claims, 0)

    def test_traceability_score(self):
        self.ge.add_source("doc1", "Functions are first class citizens in Python")
        result = self.ge.ground(["Functions in Python are first class"])
        self.assertGreater(result.traceability_score, 0.0)

    def test_ground_empty(self):
        result = self.ge.ground([])
        self.assertEqual(result.total_claims, 0)
        self.assertEqual(result.traceability_score, 0.0)

    def test_history(self):
        self.ge.ground([])
        self.ge.ground([])
        self.assertEqual(len(self.ge.history()), 2)

    def test_summary(self):
        self.ge.add_source("s1", "content")
        s = self.ge.summary()
        self.assertEqual(s["sources"], 1)

    def test_ground_claim_empty(self):
        citation = self.ge.ground_claim("")
        self.assertIsNone(citation)


if __name__ == "__main__":
    unittest.main()
