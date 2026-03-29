"""Tests for NotebookAgent (Task 704)."""
import unittest

from lidco.notebook.agent import NotebookAgent
from lidco.notebook.editor import NotebookEditor
from lidco.notebook.parser import Cell, CellOutput, NotebookDoc


def _doc(*sources, cell_type="code"):
    return NotebookDoc(cells=[Cell(cell_type=cell_type, source=s) for s in sources])


class TestExecutePlanAddCodeCell(unittest.TestCase):
    def setUp(self):
        self.agent = NotebookAgent()

    def test_add_code_cell(self):
        doc = _doc("x = 1")
        result = self.agent.execute_plan("add code cell", doc)
        self.assertEqual(len(result.cells), 2)
        self.assertEqual(result.cells[1].cell_type, "code")

    def test_add_a_cell(self):
        doc = _doc("x = 1")
        result = self.agent.execute_plan("add a cell", doc)
        self.assertEqual(len(result.cells), 2)

    def test_add_cell(self):
        doc = _doc()
        doc = NotebookDoc(cells=[])
        result = self.agent.execute_plan("add cell", doc)
        self.assertEqual(len(result.cells), 1)
        self.assertEqual(result.cells[0].cell_type, "code")


class TestExecutePlanAddMarkdown(unittest.TestCase):
    def setUp(self):
        self.agent = NotebookAgent()

    def test_add_markdown(self):
        doc = _doc("x")
        result = self.agent.execute_plan("add markdown # Hello", doc)
        self.assertEqual(result.cells[-1].cell_type, "markdown")
        self.assertIn("Hello", result.cells[-1].source)

    def test_add_markdown_empty(self):
        doc = _doc("x")
        result = self.agent.execute_plan("add markdown", doc)
        self.assertEqual(result.cells[-1].cell_type, "markdown")


class TestExecutePlanDelete(unittest.TestCase):
    def setUp(self):
        self.agent = NotebookAgent()

    def test_delete_cell_1(self):
        doc = _doc("a", "b", "c")
        result = self.agent.execute_plan("delete cell 2", doc)
        self.assertEqual(len(result.cells), 2)
        self.assertEqual(result.cells[0].source, "a")
        self.assertEqual(result.cells[1].source, "c")

    def test_delete_cell_first(self):
        doc = _doc("a", "b")
        result = self.agent.execute_plan("delete cell 1", doc)
        self.assertEqual(len(result.cells), 1)
        self.assertEqual(result.cells[0].source, "b")


class TestExecutePlanFix(unittest.TestCase):
    def setUp(self):
        self.agent = NotebookAgent()

    def test_fix_cell(self):
        doc = _doc("buggy code")
        result = self.agent.execute_plan("fix cell 1", doc)
        self.assertIn("# fixed", result.cells[0].source)
        self.assertIn("buggy code", result.cells[0].source)


class TestExecutePlanClearOutputs(unittest.TestCase):
    def setUp(self):
        self.agent = NotebookAgent()

    def test_clear_outputs(self):
        cell = Cell(
            cell_type="code",
            source="x",
            outputs=[CellOutput(output_type="stream", text="out")],
        )
        doc = NotebookDoc(cells=[cell])
        result = self.agent.execute_plan("clear outputs", doc)
        self.assertEqual(result.cells[0].outputs, [])

    def test_clear_all_outputs(self):
        cell = Cell(cell_type="code", source="x", outputs=[CellOutput(output_type="stream", text="a")])
        doc = NotebookDoc(cells=[cell])
        result = self.agent.execute_plan("clear all outputs", doc)
        self.assertEqual(result.cells[0].outputs, [])


class TestExecutePlanFallback(unittest.TestCase):
    def setUp(self):
        self.agent = NotebookAgent()

    def test_unknown_instruction_appends_markdown(self):
        doc = _doc("x")
        result = self.agent.execute_plan("do something unusual", doc)
        self.assertEqual(len(result.cells), 2)
        self.assertEqual(result.cells[-1].cell_type, "markdown")
        self.assertIn("do something unusual", result.cells[-1].source)


class TestExecutePlanImmutability(unittest.TestCase):
    def test_original_doc_unchanged(self):
        agent = NotebookAgent()
        doc = _doc("a", "b")
        agent.execute_plan("add code cell", doc)
        self.assertEqual(len(doc.cells), 2)


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.agent = NotebookAgent()

    def test_analyze_counts(self):
        doc = NotebookDoc(cells=[
            Cell(cell_type="code", source="x = 1"),
            Cell(cell_type="markdown", source="# Title"),
            Cell(cell_type="code", source="y = 2"),
        ])
        result = self.agent.analyze(doc)
        self.assertEqual(result["total_cells"], 3)
        self.assertEqual(result["code_cells"], 2)
        self.assertEqual(result["markdown_cells"], 1)

    def test_analyze_has_outputs_false(self):
        doc = _doc("x")
        result = self.agent.analyze(doc)
        self.assertFalse(result["has_outputs"])

    def test_analyze_has_outputs_true(self):
        cell = Cell(
            cell_type="code",
            source="x",
            outputs=[CellOutput(output_type="stream", text="hi")],
        )
        doc = NotebookDoc(cells=[cell])
        result = self.agent.analyze(doc)
        self.assertTrue(result["has_outputs"])

    def test_analyze_cell_summary(self):
        doc = _doc("print('hello')")
        result = self.agent.analyze(doc)
        self.assertEqual(len(result["cell_summary"]), 1)
        self.assertIn("code", result["cell_summary"][0])

    def test_analyze_empty_notebook(self):
        doc = NotebookDoc(cells=[])
        result = self.agent.analyze(doc)
        self.assertEqual(result["total_cells"], 0)
        self.assertEqual(result["cell_summary"], [])


class TestCustomEditor(unittest.TestCase):
    def test_injected_editor_used(self):
        editor = NotebookEditor()
        agent = NotebookAgent(editor=editor)
        doc = _doc("x")
        result = agent.execute_plan("add code cell", doc)
        self.assertEqual(len(result.cells), 2)


class TestAnalyzeEdgeCases(unittest.TestCase):
    def setUp(self):
        self.agent = NotebookAgent()

    def test_analyze_only_markdown(self):
        doc = NotebookDoc(cells=[
            Cell(cell_type="markdown", source="# A"),
            Cell(cell_type="markdown", source="# B"),
        ])
        result = self.agent.analyze(doc)
        self.assertEqual(result["code_cells"], 0)
        self.assertEqual(result["markdown_cells"], 2)
        self.assertFalse(result["has_outputs"])

    def test_analyze_cell_summary_truncates_long_source(self):
        long_source = "x" * 200
        doc = NotebookDoc(cells=[Cell(cell_type="code", source=long_source)])
        result = self.agent.analyze(doc)
        # Summary preview is at most 60 chars of source
        summary = result["cell_summary"][0]
        self.assertIn("code", summary)
        self.assertLessEqual(len(summary), 200)

    def test_execute_plan_fix_preserves_other_cells(self):
        doc = _doc("a", "buggy", "c")
        result = self.agent.execute_plan("fix cell 2", doc)
        self.assertEqual(result.cells[0].source, "a")
        self.assertIn("# fixed", result.cells[1].source)
        self.assertEqual(result.cells[2].source, "c")


if __name__ == "__main__":
    unittest.main()
