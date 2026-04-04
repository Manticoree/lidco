"""Tests for lidco.verify.evidence — EvidenceLinker."""
from __future__ import annotations

import unittest

from lidco.verify.evidence import EvidenceLinker, EvidenceLink


class TestEvidenceLinker(unittest.TestCase):
    def setUp(self):
        self.linker = EvidenceLinker()

    # -- add_evidence + link -----------------------------------------------

    def test_link_returns_none_when_empty(self):
        self.assertIsNone(self.linker.link("some claim"))

    def test_link_finds_matching_evidence(self):
        self.linker.add_evidence("doc1", "The server crashed at midnight")
        link = self.linker.link("The server crashed")
        self.assertIsNotNone(link)
        self.assertIsInstance(link, EvidenceLink)
        self.assertEqual(link.source, "doc1")
        self.assertGreater(link.strength, 0)

    def test_link_best_match(self):
        self.linker.add_evidence("src1", "apples and oranges")
        self.linker.add_evidence("src2", "the server crashed and burned")
        link = self.linker.link("the server crashed")
        self.assertEqual(link.source, "src2")

    def test_link_no_match_unrelated(self):
        self.linker.add_evidence("src", "bananas are yellow fruit")
        result = self.linker.link("quantum entanglement theory")
        self.assertIsNone(result)

    def test_link_returns_none_for_short_words_only(self):
        result = self.linker.link("a b c")
        self.assertIsNone(result)

    # -- coverage ----------------------------------------------------------

    def test_coverage_empty_claims(self):
        self.assertEqual(self.linker.coverage([]), 1.0)

    def test_coverage_all_linked(self):
        self.linker.add_evidence("doc", "server performance issues detected")
        cov = self.linker.coverage(["server performance"])
        self.assertEqual(cov, 1.0)

    def test_coverage_partial(self):
        self.linker.add_evidence("doc", "server crashed")
        cov = self.linker.coverage(["server crashed", "quantum physics advances"])
        self.assertEqual(cov, 0.5)

    # -- unlinked ----------------------------------------------------------

    def test_unlinked_empty(self):
        self.linker.add_evidence("doc", "server crashed heavily")
        self.assertEqual(self.linker.unlinked(["server crashed"]), [])

    def test_unlinked_returns_unmatched(self):
        self.linker.add_evidence("doc", "server crashed")
        result = self.linker.unlinked(["server crashed", "quantum leap"])
        self.assertEqual(result, ["quantum leap"])

    def test_evidence_link_fields(self):
        link = EvidenceLink(claim="c", source="s", content="ct", strength=0.8)
        self.assertEqual(link.claim, "c")
        self.assertEqual(link.strength, 0.8)


if __name__ == "__main__":
    unittest.main()
