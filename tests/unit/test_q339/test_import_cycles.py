"""Tests for ImportCycleDetector (Q339)."""
from __future__ import annotations

import unittest

from lidco.stability.import_cycles import ImportCycleDetector


class TestBuildGraph(unittest.TestCase):
    def setUp(self):
        self.det = ImportCycleDetector()

    def test_build_returns_dict(self):
        modules = {"a": ["b"], "b": ["c"], "c": []}
        graph = self.det.build_graph(modules)
        self.assertIsInstance(graph, dict)

    def test_all_modules_present(self):
        modules = {"a": ["b"], "b": ["c"], "c": []}
        graph = self.det.build_graph(modules)
        self.assertIn("a", graph)
        self.assertIn("b", graph)
        self.assertIn("c", graph)

    def test_referenced_but_undefined_module_added(self):
        modules = {"a": ["b"]}
        graph = self.det.build_graph(modules)
        # "b" is referenced but not defined — should be added with empty deps.
        self.assertIn("b", graph)
        self.assertEqual(graph["b"], [])

    def test_empty_modules(self):
        graph = self.det.build_graph({})
        self.assertEqual(graph, {})


class TestDetectCycles(unittest.TestCase):
    def setUp(self):
        self.det = ImportCycleDetector()

    def test_simple_cycle_detected(self):
        modules = {"a": ["b"], "b": ["a"]}
        self.det.build_graph(modules)
        cycles = self.det.detect_cycles()
        self.assertGreater(len(cycles), 0)

    def test_no_cycle_in_dag(self):
        modules = {"a": ["b", "c"], "b": ["c"], "c": []}
        self.det.build_graph(modules)
        cycles = self.det.detect_cycles()
        self.assertEqual(cycles, [])

    def test_three_node_cycle(self):
        modules = {"a": ["b"], "b": ["c"], "c": ["a"]}
        self.det.build_graph(modules)
        cycles = self.det.detect_cycles()
        self.assertGreater(len(cycles), 0)
        # Cycle should include all three nodes.
        flat = [n for cycle in cycles for n in cycle]
        self.assertTrue({"a", "b", "c"}.issubset(set(flat)))

    def test_self_cycle(self):
        modules = {"a": ["a"]}
        self.det.build_graph(modules)
        cycles = self.det.detect_cycles()
        self.assertGreater(len(cycles), 0)

    def test_returns_list_of_lists(self):
        modules = {"x": ["y"], "y": ["x"]}
        self.det.build_graph(modules)
        cycles = self.det.detect_cycles()
        self.assertIsInstance(cycles, list)
        for c in cycles:
            self.assertIsInstance(c, list)

    def test_no_duplicate_cycles(self):
        modules = {"a": ["b"], "b": ["a"]}
        self.det.build_graph(modules)
        cycles = self.det.detect_cycles()
        # Should not have the same cycle twice.
        seen = set()
        for c in cycles:
            key = tuple(sorted(c))
            self.assertNotIn(key, seen)
            seen.add(key)


class TestSuggestBreaks(unittest.TestCase):
    def setUp(self):
        self.det = ImportCycleDetector()

    def test_suggest_for_each_cycle(self):
        modules = {"a": ["b"], "b": ["a"]}
        self.det.build_graph(modules)
        cycles = self.det.detect_cycles()
        suggestions = self.det.suggest_breaks(cycles)
        self.assertEqual(len(suggestions), len(cycles))

    def test_result_keys(self):
        modules = {"a": ["b"], "b": ["a"]}
        self.det.build_graph(modules)
        cycles = self.det.detect_cycles()
        suggestions = self.det.suggest_breaks(cycles)
        for s in suggestions:
            self.assertIn("cycle", s)
            self.assertIn("suggestion", s)
            self.assertIn("break_point", s)

    def test_break_point_is_in_cycle(self):
        modules = {"a": ["b", "c"], "b": ["a"]}
        self.det.build_graph(modules)
        cycles = self.det.detect_cycles()
        suggestions = self.det.suggest_breaks(cycles)
        for s in suggestions:
            self.assertIn(s["break_point"], s["cycle"])

    def test_empty_cycles_returns_empty(self):
        suggestions = self.det.suggest_breaks([])
        self.assertEqual(suggestions, [])


class TestLazyImportHelper(unittest.TestCase):
    def setUp(self):
        self.det = ImportCycleDetector()

    def test_returns_string(self):
        snippet = self.det.lazy_import_helper("mypackage.mymodule")
        self.assertIsInstance(snippet, str)

    def test_contains_import(self):
        snippet = self.det.lazy_import_helper("mypackage.mymodule")
        self.assertIn("import mypackage.mymodule", snippet)

    def test_contains_def(self):
        snippet = self.det.lazy_import_helper("utils")
        self.assertIn("def ", snippet)

    def test_dot_converted_to_underscore_in_func_name(self):
        snippet = self.det.lazy_import_helper("a.b.c")
        self.assertIn("_import_a_b_c", snippet)


if __name__ == "__main__":
    unittest.main()
