"""Tests for lidco.adr.generator — ADRGenerator."""

from __future__ import annotations

import unittest

from lidco.adr.generator import (
    ADRGenerator,
    DiscussionEntry,
    GenerationResult,
    _compute_confidence,
    _extract_section,
    _extract_title,
    _score_sentence,
)
from lidco.adr.manager import ADRManager


class TestScoreSentence(unittest.TestCase):
    """Tests for _score_sentence helper."""

    def test_match(self) -> None:
        score = _score_sentence("we need a database because of performance", ["because", "we need"])
        self.assertGreater(score, 0)

    def test_no_match(self) -> None:
        score = _score_sentence("hello world", ["because", "since"])
        self.assertEqual(score, 0.0)


class TestExtractSection(unittest.TestCase):
    """Tests for _extract_section helper."""

    def test_extracts_matching_sentences(self) -> None:
        entries = [
            DiscussionEntry(author="A", content="We need a cache because latency is high. The sky is blue."),
        ]
        result = _extract_section(entries, ["because", "we need"])
        self.assertIn("cache", result.lower())

    def test_empty_entries(self) -> None:
        result = _extract_section([], ["because"])
        self.assertEqual(result, "")


class TestExtractTitle(unittest.TestCase):
    """Tests for _extract_title helper."""

    def test_uses_first_sentence(self) -> None:
        entries = [DiscussionEntry(author="A", content="Use Redis for caching. It is fast.")]
        title = _extract_title(entries)
        self.assertEqual(title, "Use Redis for caching")

    def test_empty_entries(self) -> None:
        title = _extract_title([])
        self.assertEqual(title, "Untitled Decision")

    def test_long_content_truncated(self) -> None:
        entries = [DiscussionEntry(author="A", content="x" * 200)]
        title = _extract_title(entries)
        self.assertLessEqual(len(title), 80)


class TestComputeConfidence(unittest.TestCase):
    """Tests for _compute_confidence helper."""

    def test_all_sections(self) -> None:
        c = _compute_confidence("ctx", "dec", "cons")
        self.assertGreater(c, 0.9)

    def test_no_sections(self) -> None:
        c = _compute_confidence("", "", "")
        self.assertEqual(c, 0.0)

    def test_partial(self) -> None:
        c = _compute_confidence("ctx", "", "")
        self.assertGreater(c, 0)
        self.assertLess(c, 1.0)


class TestDiscussionEntry(unittest.TestCase):
    """Tests for DiscussionEntry."""

    def test_to_dict(self) -> None:
        e = DiscussionEntry(author="A", content="text", role="architect")
        d = e.to_dict()
        self.assertEqual(d["author"], "A")
        self.assertEqual(d["role"], "architect")


class TestGenerationResult(unittest.TestCase):
    """Tests for GenerationResult."""

    def test_to_dict(self) -> None:
        from lidco.adr.manager import ADR
        adr = ADR(number=1, title="T")
        r = GenerationResult(adr=adr, extracted_context="c", extracted_decision="d", extracted_consequences="e", confidence=0.8, source_entries=3)
        d = r.to_dict()
        self.assertEqual(d["confidence"], 0.8)
        self.assertEqual(d["source_entries"], 3)


class TestADRGenerator(unittest.TestCase):
    """Tests for ADRGenerator."""

    def setUp(self) -> None:
        self.gen = ADRGenerator()

    def test_generate_from_discussion(self) -> None:
        entries = [
            DiscussionEntry(author="Alice", content="We need caching because latency is too high."),
            DiscussionEntry(author="Bob", content="We decided to use Redis. The consequence is operational complexity."),
        ]
        result = self.gen.generate_from_discussion(entries, title="Use Redis")
        self.assertEqual(result.adr.title, "Use Redis")
        self.assertEqual(result.source_entries, 2)
        self.assertGreater(result.confidence, 0)

    def test_generate_from_discussion_auto_title(self) -> None:
        entries = [
            DiscussionEntry(author="A", content="Adopt microservices architecture. Better scalability."),
        ]
        result = self.gen.generate_from_discussion(entries)
        self.assertIn("microservices", result.adr.title.lower())

    def test_generate_from_discussion_auto_authors(self) -> None:
        entries = [
            DiscussionEntry(author="Alice", content="Something."),
            DiscussionEntry(author="Bob", content="Another."),
        ]
        result = self.gen.generate_from_discussion(entries)
        self.assertIn("Alice", result.adr.authors)
        self.assertIn("Bob", result.adr.authors)

    def test_generate_from_discussion_empty(self) -> None:
        with self.assertRaises(ValueError):
            self.gen.generate_from_discussion([])

    def test_generate_from_text(self) -> None:
        result = self.gen.generate_from_text(
            "We will use GraphQL because REST is too chatty. The consequence is a steeper learning curve.",
            title="Use GraphQL",
            author="Dev",
        )
        self.assertEqual(result.adr.title, "Use GraphQL")
        self.assertEqual(result.source_entries, 1)

    def test_generate_from_text_empty(self) -> None:
        with self.assertRaises(ValueError):
            self.gen.generate_from_text("")

    def test_generate_markdown(self) -> None:
        result = self.gen.generate_from_text("We decided to use TypeScript.", title="TS")
        md = self.gen.generate_markdown(result)
        self.assertIn("ADR-", md)
        self.assertIn("TS", md)

    def test_manager_property(self) -> None:
        mgr = ADRManager()
        gen = ADRGenerator(manager=mgr)
        self.assertIs(gen.manager, mgr)

    def test_generate_with_tags(self) -> None:
        result = self.gen.generate_from_text("Some text about approach.", title="T", tags=["lang"])
        self.assertIn("lang", result.adr.tags)


if __name__ == "__main__":
    unittest.main()
