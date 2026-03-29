"""Tests for NotebookEditor (Task 703)."""
import unittest

from lidco.notebook.editor import NotebookEditError, NotebookEditor
from lidco.notebook.parser import Cell, CellOutput, NotebookDoc


def _doc(*sources, cell_type="code"):
    """Build a NotebookDoc with cells having given sources."""
    return NotebookDoc(cells=[Cell(cell_type=cell_type, source=s) for s in sources])


class TestAppendCell(unittest.TestCase):
    def setUp(self):
        self.editor = NotebookEditor()

    def test_append_to_empty(self):
        doc = _doc()
        # _doc() creates no-arg cells -- let's use a truly empty doc
        doc = NotebookDoc(cells=[])
        result = self.editor.append_cell(doc, "code", "x = 1")
        self.assertEqual(len(result.cells), 1)
        self.assertEqual(result.cells[0].source, "x = 1")

    def test_append_preserves_existing(self):
        doc = _doc("a", "b")
        result = self.editor.append_cell(doc, "code", "c")
        self.assertEqual(len(result.cells), 3)
        self.assertEqual(result.cells[0].source, "a")
        self.assertEqual(result.cells[2].source, "c")

    def test_append_does_not_mutate(self):
        doc = _doc("a")
        result = self.editor.append_cell(doc, "code", "b")
        self.assertEqual(len(doc.cells), 1)
        self.assertEqual(len(result.cells), 2)

    def test_append_markdown_cell(self):
        doc = NotebookDoc(cells=[])
        result = self.editor.append_cell(doc, "markdown", "# Title")
        self.assertEqual(result.cells[0].cell_type, "markdown")


class TestReplaceCell(unittest.TestCase):
    def setUp(self):
        self.editor = NotebookEditor()

    def test_replace_first_cell(self):
        doc = _doc("old", "keep")
        result = self.editor.replace_cell(doc, 0, "new")
        self.assertEqual(result.cells[0].source, "new")
        self.assertEqual(result.cells[1].source, "keep")

    def test_replace_last_cell(self):
        doc = _doc("a", "b", "c")
        result = self.editor.replace_cell(doc, 2, "z")
        self.assertEqual(result.cells[2].source, "z")

    def test_replace_does_not_mutate(self):
        doc = _doc("old")
        self.editor.replace_cell(doc, 0, "new")
        self.assertEqual(doc.cells[0].source, "old")

    def test_replace_negative_index_raises(self):
        doc = _doc("a")
        with self.assertRaises(NotebookEditError):
            self.editor.replace_cell(doc, -1, "x")

    def test_replace_out_of_bounds_raises(self):
        doc = _doc("a")
        with self.assertRaises(NotebookEditError):
            self.editor.replace_cell(doc, 5, "x")

    def test_replace_empty_doc_raises(self):
        doc = NotebookDoc(cells=[])
        with self.assertRaises(NotebookEditError):
            self.editor.replace_cell(doc, 0, "x")


class TestDeleteCell(unittest.TestCase):
    def setUp(self):
        self.editor = NotebookEditor()

    def test_delete_only_cell(self):
        doc = _doc("a")
        result = self.editor.delete_cell(doc, 0)
        self.assertEqual(len(result.cells), 0)

    def test_delete_middle_cell(self):
        doc = _doc("a", "b", "c")
        result = self.editor.delete_cell(doc, 1)
        self.assertEqual(len(result.cells), 2)
        self.assertEqual(result.cells[0].source, "a")
        self.assertEqual(result.cells[1].source, "c")

    def test_delete_does_not_mutate(self):
        doc = _doc("a", "b")
        self.editor.delete_cell(doc, 0)
        self.assertEqual(len(doc.cells), 2)

    def test_delete_out_of_bounds_raises(self):
        doc = _doc("a")
        with self.assertRaises(NotebookEditError):
            self.editor.delete_cell(doc, 1)

    def test_delete_negative_raises(self):
        doc = _doc("a")
        with self.assertRaises(NotebookEditError):
            self.editor.delete_cell(doc, -1)


class TestMoveCell(unittest.TestCase):
    def setUp(self):
        self.editor = NotebookEditor()

    def test_move_first_to_last(self):
        doc = _doc("a", "b", "c")
        result = self.editor.move_cell(doc, 0, 2)
        self.assertEqual(result.cells[0].source, "b")
        self.assertEqual(result.cells[2].source, "a")

    def test_move_same_position(self):
        doc = _doc("a", "b")
        result = self.editor.move_cell(doc, 0, 0)
        self.assertEqual(result.cells[0].source, "a")

    def test_move_does_not_mutate(self):
        doc = _doc("a", "b")
        self.editor.move_cell(doc, 0, 1)
        self.assertEqual(doc.cells[0].source, "a")

    def test_move_from_oob_raises(self):
        doc = _doc("a")
        with self.assertRaises(NotebookEditError):
            self.editor.move_cell(doc, 5, 0)

    def test_move_to_oob_raises(self):
        doc = _doc("a")
        with self.assertRaises(NotebookEditError):
            self.editor.move_cell(doc, 0, 5)


class TestInsertCell(unittest.TestCase):
    def setUp(self):
        self.editor = NotebookEditor()

    def test_insert_at_beginning(self):
        doc = _doc("b")
        result = self.editor.insert_cell(doc, 0, "code", "a")
        self.assertEqual(len(result.cells), 2)
        self.assertEqual(result.cells[0].source, "a")
        self.assertEqual(result.cells[1].source, "b")

    def test_insert_at_end(self):
        doc = _doc("a")
        result = self.editor.insert_cell(doc, 1, "code", "b")
        self.assertEqual(result.cells[1].source, "b")

    def test_insert_does_not_mutate(self):
        doc = _doc("a")
        self.editor.insert_cell(doc, 0, "code", "z")
        self.assertEqual(len(doc.cells), 1)

    def test_insert_negative_raises(self):
        doc = _doc("a")
        with self.assertRaises(NotebookEditError):
            self.editor.insert_cell(doc, -1, "code", "x")

    def test_insert_far_oob_raises(self):
        doc = _doc("a")
        with self.assertRaises(NotebookEditError):
            self.editor.insert_cell(doc, 10, "code", "x")


class TestClearOutputs(unittest.TestCase):
    def setUp(self):
        self.editor = NotebookEditor()

    def test_clear_removes_outputs(self):
        cell = Cell(
            cell_type="code",
            source="x",
            outputs=[CellOutput(output_type="stream", text="hi")],
            execution_count=1,
        )
        doc = NotebookDoc(cells=[cell])
        result = self.editor.clear_outputs(doc)
        self.assertEqual(result.cells[0].outputs, [])
        self.assertIsNone(result.cells[0].execution_count)

    def test_clear_does_not_mutate(self):
        cell = Cell(
            cell_type="code",
            source="x",
            outputs=[CellOutput(output_type="stream", text="hi")],
        )
        doc = NotebookDoc(cells=[cell])
        self.editor.clear_outputs(doc)
        self.assertEqual(len(doc.cells[0].outputs), 1)

    def test_clear_empty_notebook(self):
        doc = NotebookDoc(cells=[])
        result = self.editor.clear_outputs(doc)
        self.assertEqual(len(result.cells), 0)


class TestApplySourceEdit(unittest.TestCase):
    def test_apply_source_edit_same_as_replace(self):
        editor = NotebookEditor()
        doc = _doc("old")
        result = editor.apply_source_edit(doc, 0, "new")
        self.assertEqual(result.cells[0].source, "new")


if __name__ == "__main__":
    unittest.main()
