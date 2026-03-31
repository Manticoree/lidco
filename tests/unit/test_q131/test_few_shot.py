"""Tests for Q131 FewShotSelector."""
from __future__ import annotations
import unittest
from lidco.prompts.few_shot import FewShotSelector, FewShotExample


class TestFewShotExample(unittest.TestCase):
    def test_defaults(self):
        ex = FewShotExample(input="q", output="a")
        self.assertEqual(ex.description, "")

    def test_full(self):
        ex = FewShotExample(input="q", output="a", description="desc")
        self.assertEqual(ex.description, "desc")


class TestFewShotSelector(unittest.TestCase):
    def setUp(self):
        self.selector = FewShotSelector()

    def _make_examples(self):
        return [
            FewShotExample(input="add numbers one two", output="3"),
            FewShotExample(input="subtract numbers five three", output="2"),
            FewShotExample(input="multiply numbers four two", output="8"),
        ]

    def test_add_example(self):
        self.selector.add(FewShotExample(input="x", output="y"))
        results = self.selector.select("x", n=1)
        self.assertEqual(len(results), 1)

    def test_select_n(self):
        for ex in self._make_examples():
            self.selector.add(ex)
        results = self.selector.select("numbers", n=2)
        self.assertEqual(len(results), 2)

    def test_select_by_relevance(self):
        for ex in self._make_examples():
            self.selector.add(ex)
        results = self.selector.select("add numbers", n=1)
        self.assertEqual(results[0].input, "add numbers one two")

    def test_select_returns_at_most_n(self):
        self.selector.add(FewShotExample(input="only one", output="yes"))
        results = self.selector.select("one", n=5)
        self.assertLessEqual(len(results), 1)

    def test_select_empty_query(self):
        for ex in self._make_examples():
            self.selector.add(ex)
        results = self.selector.select("", n=2)
        self.assertEqual(len(results), 2)

    def test_format_qa(self):
        ex = FewShotExample(input="What is 2+2?", output="4")
        result = self.selector.format([ex], style="qa")
        self.assertIn("Q:", result)
        self.assertIn("A:", result)
        self.assertIn("What is 2+2?", result)
        self.assertIn("4", result)

    def test_format_xml(self):
        ex = FewShotExample(input="What is 2+2?", output="4")
        result = self.selector.format([ex], style="xml")
        self.assertIn("<example>", result)
        self.assertIn("<input>", result)
        self.assertIn("<output>", result)
        self.assertIn("What is 2+2?", result)

    def test_format_multiple(self):
        examples = [
            FewShotExample(input="q1", output="a1"),
            FewShotExample(input="q2", output="a2"),
        ]
        result = self.selector.format(examples, style="qa")
        self.assertIn("q1", result)
        self.assertIn("q2", result)

    def test_format_empty(self):
        result = self.selector.format([], style="qa")
        self.assertEqual(result, "")

    def test_load_from_dict(self):
        data = [{"input": "hi", "output": "hello"}, {"input": "bye", "output": "goodbye"}]
        self.selector.load_from_dict(data)
        results = self.selector.select("hi", n=5)
        inputs = [r.input for r in results]
        self.assertIn("hi", inputs)

    def test_load_from_dict_with_description(self):
        data = [{"input": "x", "output": "y", "description": "test"}]
        self.selector.load_from_dict(data)
        results = self.selector.select("x", n=1)
        self.assertEqual(results[0].description, "test")

    def test_init_with_examples(self):
        examples = self._make_examples()
        selector = FewShotSelector(examples=examples)
        results = selector.select("multiply", n=1)
        self.assertEqual(results[0].input, "multiply numbers four two")

    def test_select_no_examples(self):
        results = self.selector.select("query", n=3)
        self.assertEqual(results, [])

    def test_format_default_style(self):
        ex = FewShotExample(input="q", output="a")
        result = self.selector.format([ex])
        self.assertIn("Q:", result)


if __name__ == "__main__":
    unittest.main()
