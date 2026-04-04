"""Tests for lidco.adaptive.selector — ExampleSelector."""
from __future__ import annotations

import unittest

from lidco.adaptive.selector import ExampleSelector, Example


class TestExampleSelector(unittest.TestCase):
    def setUp(self):
        self.selector = ExampleSelector()

    def test_add_and_examples(self):
        ex = Example(input_text="in", output_text="out", task_type="code")
        self.selector.add_example(ex)
        self.assertEqual(len(self.selector.examples()), 1)

    def test_clear(self):
        self.selector.add_example(Example(input_text="a", output_text="b"))
        self.selector.clear()
        self.assertEqual(len(self.selector.examples()), 0)

    def test_select_by_task_type(self):
        self.selector.add_example(Example(input_text="x", output_text="y", task_type="code"))
        self.selector.add_example(Example(input_text="a", output_text="b", task_type="debug"))
        self.selector.add_example(Example(input_text="m", output_text="n", task_type="code"))
        selected = self.selector.select("code", k=5)
        # code examples should come first
        self.assertEqual(selected[0].task_type, "code")
        self.assertEqual(selected[1].task_type, "code")

    def test_select_k_limit(self):
        for i in range(10):
            self.selector.add_example(Example(input_text=f"in{i}", output_text=f"out{i}", task_type="code"))
        selected = self.selector.select("code", k=3)
        self.assertEqual(len(selected), 3)

    def test_select_with_difficulty(self):
        self.selector.add_example(Example(input_text="easy", output_text="e", task_type="code", difficulty=1))
        self.selector.add_example(Example(input_text="hard", output_text="h", task_type="code", difficulty=3))
        selected = self.selector.select("code", k=2, difficulty=3)
        self.assertEqual(selected[0].input_text, "hard")

    def test_select_with_tags(self):
        self.selector.add_example(Example(input_text="py", output_text="o", task_type="code", tags=["python", "sort"]))
        self.selector.add_example(Example(input_text="js", output_text="o", task_type="code", tags=["javascript"]))
        selected = self.selector.select("code", k=2, tags=["python"])
        self.assertEqual(selected[0].input_text, "py")

    def test_select_empty(self):
        selected = self.selector.select("code", k=3)
        self.assertEqual(selected, [])

    def test_select_diversity_dedup(self):
        # Add duplicates
        self.selector.add_example(Example(input_text="same", output_text="a", task_type="code"))
        self.selector.add_example(Example(input_text="same", output_text="b", task_type="code"))
        self.selector.add_example(Example(input_text="diff", output_text="c", task_type="code"))
        selected = self.selector.select("code", k=3)
        # Should deduplicate by input_text
        inputs = [ex.input_text for ex in selected]
        self.assertEqual(len(set(inputs)), len(inputs))

    def test_select_general_fallback(self):
        self.selector.add_example(Example(input_text="gen", output_text="g", task_type="general"))
        selected = self.selector.select("nonexistent", k=1)
        # Should still return general (lower score but still returned)
        self.assertEqual(len(selected), 1)


if __name__ == "__main__":
    unittest.main()
