"""Tests for auto_suggestion — Q126."""
from __future__ import annotations
import unittest
from lidco.proactive.auto_suggestion import AutoSuggestion, AutoSuggestionResult
from lidco.proactive.suggestion_engine import SuggestionEngine, Suggestion
from lidco.proactive.smell_detector import SmellDetector, Smell


class TestAutoSuggestionResult(unittest.TestCase):
    def test_total_empty(self):
        r = AutoSuggestionResult()
        self.assertEqual(r.total, 0)

    def test_total(self):
        r = AutoSuggestionResult(
            suggestions=[Suggestion("a", "refactor", "m")],
            smells=[Smell("long_method", "f:1", "d", "medium")],
        )
        self.assertEqual(r.total, 2)


class TestAutoSuggestion(unittest.TestCase):
    def setUp(self):
        self.auto = AutoSuggestion()

    def test_run_returns_result(self):
        result = self.auto.run("x = 1")
        self.assertIsInstance(result, AutoSuggestionResult)

    def test_run_suggestions_list(self):
        result = self.auto.run("# TODO fix this")
        self.assertIsInstance(result.suggestions, list)

    def test_run_smells_list(self):
        result = self.auto.run("def foo(): pass")
        self.assertIsInstance(result.smells, list)

    def test_run_on_files_returns_dict(self):
        files = {"a.py": "x = 1", "b.py": "# TODO"}
        result = self.auto.run_on_files(files)
        self.assertIsInstance(result, dict)

    def test_run_on_files_has_keys(self):
        files = {"a.py": "x = 1"}
        result = self.auto.run_on_files(files)
        self.assertIn("a.py", result)

    def test_run_on_files_values_are_results(self):
        files = {"a.py": "# TODO fix"}
        result = self.auto.run_on_files(files)
        self.assertIsInstance(result["a.py"], AutoSuggestionResult)

    def test_summary_returns_string(self):
        files = {"a.py": "x = 1"}
        results = self.auto.run_on_files(files)
        s = self.auto.summary(results)
        self.assertIsInstance(s, str)

    def test_summary_contains_count(self):
        files = {"a.py": "x = 1"}
        results = self.auto.run_on_files(files)
        s = self.auto.summary(results)
        self.assertIn("1 file", s)

    def test_run_with_todo_finds_suggestion(self):
        result = self.auto.run("# TODO refactor everything")
        self.assertTrue(len(result.suggestions) > 0)

    def test_run_empty_code(self):
        result = self.auto.run("")
        self.assertIsInstance(result, AutoSuggestionResult)

    def test_custom_engine(self):
        custom = SuggestionEngine(rules=[])
        auto = AutoSuggestion(engine=custom)
        result = auto.run("# TODO")
        self.assertEqual(result.suggestions, [])

    def test_custom_detector(self):
        custom_d = SmellDetector()
        auto = AutoSuggestion(detector=custom_d)
        result = auto.run("x = 1")
        self.assertIsInstance(result.smells, list)

    def test_run_on_files_duplicate_detection(self):
        block = "\n".join([f"x_{i} = {i}" for i in range(5)])
        files = {"a.py": block + "\n# a", "b.py": block + "\n# b"}
        results = self.auto.run_on_files(files)
        # duplicates stored under __duplicates__ key
        self.assertIn("__duplicates__", results)

    def test_summary_format(self):
        files = {"a.py": "# TODO fix", "b.py": "x = 1"}
        results = self.auto.run_on_files(files)
        s = self.auto.summary(results)
        self.assertIn("Suggestions:", s)
        self.assertIn("Smells:", s)

    def test_total_property(self):
        result = self.auto.run("# TODO fix\ntry:\n    pass\nexcept:\n    pass")
        self.assertGreater(result.total, 0)

    def test_run_on_empty_files(self):
        results = self.auto.run_on_files({})
        self.assertIsInstance(results, dict)


if __name__ == "__main__":
    unittest.main()
