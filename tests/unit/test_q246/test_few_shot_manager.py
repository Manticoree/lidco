"""Tests for lidco.prompts.few_shot_manager (Q246)."""
from __future__ import annotations

import unittest

from lidco.prompts.few_shot_manager import FewShotManager, Example


class TestFewShotManagerAdd(unittest.TestCase):
    def test_add_returns_id(self):
        mgr = FewShotManager()
        eid = mgr.add_example("in", "out")
        self.assertIsInstance(eid, str)
        self.assertEqual(len(eid), 8)

    def test_add_with_tags(self):
        mgr = FewShotManager()
        eid = mgr.add_example("in", "out", tags=["python", "test"])
        ex = mgr.list_examples()[0]
        self.assertEqual(ex.tags, ["python", "test"])

    def test_add_without_tags(self):
        mgr = FewShotManager()
        mgr.add_example("in", "out")
        ex = mgr.list_examples()[0]
        self.assertEqual(ex.tags, [])

    def test_add_multiple(self):
        mgr = FewShotManager()
        mgr.add_example("a", "b")
        mgr.add_example("c", "d")
        self.assertEqual(len(mgr.list_examples()), 2)


class TestFewShotManagerRemove(unittest.TestCase):
    def test_remove_existing(self):
        mgr = FewShotManager()
        eid = mgr.add_example("in", "out")
        self.assertTrue(mgr.remove_example(eid))
        self.assertEqual(len(mgr.list_examples()), 0)

    def test_remove_nonexistent(self):
        mgr = FewShotManager()
        self.assertFalse(mgr.remove_example("nope"))

    def test_remove_preserves_others(self):
        mgr = FewShotManager()
        e1 = mgr.add_example("a", "b")
        e2 = mgr.add_example("c", "d")
        mgr.remove_example(e1)
        remaining = mgr.list_examples()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].id, e2)


class TestFewShotManagerSelect(unittest.TestCase):
    def test_select_basic(self):
        mgr = FewShotManager()
        mgr.add_example("python function", "def foo(): pass")
        mgr.add_example("java class", "class Foo {}")
        results = mgr.select("python")
        self.assertTrue(len(results) > 0)
        self.assertIn("python", results[0].input.lower())

    def test_select_limit(self):
        mgr = FewShotManager()
        for i in range(10):
            mgr.add_example(f"example {i}", f"output {i}")
        results = mgr.select("example", limit=3)
        self.assertEqual(len(results), 3)

    def test_select_empty_query(self):
        mgr = FewShotManager()
        mgr.add_example("a", "b")
        mgr.add_example("c", "d")
        results = mgr.select("", limit=5)
        self.assertEqual(len(results), 2)

    def test_select_by_tags(self):
        mgr = FewShotManager()
        mgr.add_example("func", "impl", tags=["python"])
        mgr.add_example("class", "impl", tags=["java"])
        results = mgr.select("python", limit=1)
        self.assertEqual(len(results), 1)
        # The python-tagged one should score higher
        self.assertIn("python", results[0].tags + results[0].input.lower().split())

    def test_select_with_token_budget(self):
        mgr = FewShotManager()
        mgr.add_example("a" * 100, "b" * 100)
        mgr.add_example("c" * 100, "d" * 100)
        # Budget of 20 tokens = 80 chars, not enough for even one example (~220 chars)
        results = mgr.select("a", token_budget=20)
        self.assertEqual(len(results), 0)

    def test_select_with_generous_budget(self):
        mgr = FewShotManager()
        mgr.add_example("hello", "world")
        results = mgr.select("hello", token_budget=1000)
        self.assertEqual(len(results), 1)


class TestFewShotManagerFormat(unittest.TestCase):
    def test_format_examples(self):
        examples = [
            Example(id="1", input="What is 2+2?", output="4"),
            Example(id="2", input="What is 3+3?", output="6"),
        ]
        formatted = FewShotManager.format_examples(examples)
        self.assertIn("Input: What is 2+2?", formatted)
        self.assertIn("Output: 4", formatted)
        self.assertIn("Input: What is 3+3?", formatted)

    def test_format_empty(self):
        formatted = FewShotManager.format_examples([])
        self.assertEqual(formatted, "")

    def test_format_single(self):
        examples = [Example(id="1", input="Q", output="A")]
        formatted = FewShotManager.format_examples(examples)
        self.assertEqual(formatted, "Input: Q\nOutput: A")


class TestFewShotManagerList(unittest.TestCase):
    def test_list_empty(self):
        mgr = FewShotManager()
        self.assertEqual(mgr.list_examples(), [])

    def test_list_returns_copies(self):
        mgr = FewShotManager()
        mgr.add_example("a", "b")
        l1 = mgr.list_examples()
        l2 = mgr.list_examples()
        self.assertEqual(l1, l2)
        self.assertIsNot(l1, l2)


if __name__ == "__main__":
    unittest.main()
