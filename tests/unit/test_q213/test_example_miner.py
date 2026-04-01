"""Tests for ExampleMiner, CodeExample."""
from __future__ import annotations

import unittest

from lidco.doc_intel.example_miner import CodeExample, ExampleMiner


class TestCodeExampleFrozen(unittest.TestCase):
    def test_creation(self):
        ex = CodeExample(source="x = 1", file="test.py")
        self.assertEqual(ex.source, "x = 1")
        self.assertEqual(ex.file, "test.py")
        self.assertEqual(ex.line, 0)
        self.assertEqual(ex.function_name, "")
        self.assertAlmostEqual(ex.clarity_score, 0.5)

    def test_frozen(self):
        ex = CodeExample(source="x", file="f")
        with self.assertRaises(AttributeError):
            ex.source = "y"  # type: ignore[misc]


class TestFindExamples(unittest.TestCase):
    def test_finds_usage(self):
        src = (
            "def test_add():\n"
            "    result = add(1, 2)\n"
            "    assert result == 3\n"
        )
        miner = ExampleMiner()
        examples = miner.find_examples(src, "add", file="test_math.py")
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0].function_name, "test_add")
        self.assertEqual(examples[0].file, "test_math.py")

    def test_no_match(self):
        src = "def foo():\n    return 1\n"
        miner = ExampleMiner()
        examples = miner.find_examples(src, "bar")
        self.assertEqual(len(examples), 0)

    def test_excludes_target_definition(self):
        src = "def add(a, b):\n    return a + b\n"
        miner = ExampleMiner()
        examples = miner.find_examples(src, "add")
        self.assertEqual(len(examples), 0)

    def test_syntax_error_returns_empty(self):
        miner = ExampleMiner()
        examples = miner.find_examples("def (broken:", "foo")
        self.assertEqual(len(examples), 0)


class TestRankByClarity(unittest.TestCase):
    def test_sorts_descending(self):
        miner = ExampleMiner()
        exs = [
            CodeExample(source="a", file="f", clarity_score=0.3),
            CodeExample(source="b", file="f", clarity_score=0.9),
            CodeExample(source="c", file="f", clarity_score=0.6),
        ]
        ranked = miner.rank_by_clarity(exs)
        scores = [e.clarity_score for e in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestExtractMinimal(unittest.TestCase):
    def test_extracts_lines(self):
        src = "x = 1\nresult = add(1, 2)\ny = 3\n"
        miner = ExampleMiner()
        minimal = miner.extract_minimal(src, "add")
        self.assertIn("add(1, 2)", minimal)
        self.assertNotIn("x = 1", minimal)

    def test_empty_on_no_match(self):
        miner = ExampleMiner()
        self.assertEqual(miner.extract_minimal("x = 1", "missing"), "")


class TestAddSourceAndSearch(unittest.TestCase):
    def test_search_across_sources(self):
        miner = ExampleMiner()
        src1 = "def test_use():\n    calc = Calculator()\n    calc.run()\n"
        src2 = "def other():\n    x = Calculator()\n"
        miner.add_source("a.py", src1)
        miner.add_source("b.py", src2)
        results = miner.search("Calculator")
        self.assertEqual(len(results), 2)
        files = {r.file for r in results}
        self.assertEqual(files, {"a.py", "b.py"})

    def test_search_ranked(self):
        miner = ExampleMiner()
        miner.add_source("f.py", "def short():\n    use()\n")
        miner.add_source("g.py", "def long():\n" + "    use()\n" * 20)
        results = miner.search("use")
        # First result should have higher clarity
        if len(results) >= 2:
            self.assertGreaterEqual(results[0].clarity_score, results[-1].clarity_score)


if __name__ == "__main__":
    unittest.main()
