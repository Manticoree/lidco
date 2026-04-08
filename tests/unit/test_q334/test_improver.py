"""Tests for lidco.writing.improver — WritingImprover."""

from __future__ import annotations

import unittest

from lidco.writing.improver import (
    ImprovementResult,
    Suggestion,
    WritingImprover,
)


class TestSuggestion(unittest.TestCase):
    def test_frozen(self):
        s = Suggestion(line=1, category="grammar", original="alot", replacement="a lot", reason="Two words")
        self.assertEqual(s.line, 1)
        self.assertEqual(s.category, "grammar")


class TestImprovementResult(unittest.TestCase):
    def test_suggestion_count(self):
        r = ImprovementResult()
        self.assertEqual(r.suggestion_count, 0)
        r.suggestions.append(
            Suggestion(line=1, category="simplify", original="x", replacement="y", reason="z")
        )
        self.assertEqual(r.suggestion_count, 1)


class TestWritingImproverSimplify(unittest.TestCase):
    def setUp(self):
        self.improver = WritingImprover()

    def test_in_order_to(self):
        text = "We need to do this in order to improve quality."
        suggestions = self.improver.simplify(text)
        self.assertTrue(any(s.original.lower() == "in order to" for s in suggestions))

    def test_due_to_the_fact_that(self):
        text = "This failed due to the fact that the server was down."
        suggestions = self.improver.simplify(text)
        self.assertTrue(any("because" in s.replacement for s in suggestions))

    def test_no_simplifications(self):
        text = "The cat sat on the mat."
        suggestions = self.improver.simplify(text)
        self.assertEqual(len(suggestions), 0)

    def test_multiple_rules(self):
        text = "In order to do this at this point in time we should act."
        suggestions = self.improver.simplify(text)
        self.assertGreaterEqual(len(suggestions), 2)

    def test_line_numbers(self):
        text = "Line one.\nIn order to fix this.\nLine three."
        suggestions = self.improver.simplify(text)
        self.assertTrue(any(s.line == 2 for s in suggestions))


class TestWritingImproverGrammar(unittest.TestCase):
    def setUp(self):
        self.improver = WritingImprover()

    def test_could_of(self):
        text = "You could of done better."
        suggestions = self.improver.fix_grammar(text)
        self.assertTrue(any("could have" in s.replacement for s in suggestions))

    def test_alot(self):
        text = "There are alot of items."
        suggestions = self.improver.fix_grammar(text)
        self.assertTrue(any("a lot" in s.replacement for s in suggestions))

    def test_misspelling(self):
        text = "This is definately wrong."
        suggestions = self.improver.fix_grammar(text)
        self.assertTrue(any("definitely" in s.replacement for s in suggestions))

    def test_no_grammar_issues(self):
        text = "The implementation is correct."
        suggestions = self.improver.fix_grammar(text)
        self.assertEqual(len(suggestions), 0)


class TestWritingImproverStructure(unittest.TestCase):
    def setUp(self):
        self.improver = WritingImprover(max_sentence_words=10)

    def test_long_sentence(self):
        text = "This is a very long sentence that has way too many words in it for anyone to easily understand."
        suggestions = self.improver.check_structure(text)
        self.assertTrue(any(s.category == "structure" for s in suggestions))

    def test_short_sentences_ok(self):
        text = "Short sentence. Another short one."
        suggestions = self.improver.check_structure(text)
        self.assertEqual(len(suggestions), 0)


class TestWritingImproverApply(unittest.TestCase):
    def setUp(self):
        self.improver = WritingImprover()

    def test_apply_simplifications(self):
        text = "We need this in order to succeed."
        result = self.improver.apply_simplifications(text)
        self.assertNotIn("in order to", result.lower())
        self.assertIn("to", result.lower())

    def test_apply_multiple(self):
        text = "In order to fix the issue at this point in time we should act."
        result = self.improver.apply_simplifications(text)
        self.assertNotIn("in order to", result.lower())
        self.assertNotIn("at this point in time", result.lower())


class TestWritingImproverExamples(unittest.TestCase):
    def setUp(self):
        self.improver = WritingImprover()

    def test_suggest_example_for_technical(self):
        text = "The API endpoint accepts a JSON parameter with nested objects and arrays and returns structured data back to the caller."
        suggestions = self.improver.suggest_examples(text)
        self.assertTrue(any(s.category == "example" for s in suggestions))

    def test_no_example_needed_with_eg(self):
        text = "Use the API endpoint, e.g. GET /users, to fetch data."
        suggestions = self.improver.suggest_examples(text)
        self.assertEqual(len(suggestions), 0)

    def test_short_line_no_suggestion(self):
        text = "Use the API."
        suggestions = self.improver.suggest_examples(text)
        self.assertEqual(len(suggestions), 0)


class TestWritingImproverFull(unittest.TestCase):
    def setUp(self):
        self.improver = WritingImprover()

    def test_full_improve(self):
        text = "In order to fix this, you could of done it differently."
        result = self.improver.improve(text)
        self.assertIsInstance(result, ImprovementResult)
        self.assertGreater(result.suggestion_count, 0)
        self.assertGreater(result.original_word_count, 0)
        self.assertIsInstance(result.simplified_text, str)

    def test_custom_rules(self):
        improver = WritingImprover(simplify_rules=[("\\bfoo\\b", "bar", "test")])
        suggestions = improver.simplify("We should foo the system.")
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0].replacement, "bar")


if __name__ == "__main__":
    unittest.main()
