"""Tests for NotebookParser (Task 702)."""
import json
import os
import tempfile
import unittest

from lidco.notebook.parser import (
    Cell,
    CellDiff,
    CellOutput,
    NotebookDoc,
    NotebookParseError,
    NotebookParser,
)


def _make_nb_json(cells=None, nbformat=4, nbformat_minor=5, metadata=None):
    """Build a minimal .ipynb JSON string."""
    if cells is None:
        cells = [{"cell_type": "code", "source": "x = 1", "metadata": {}}]
    return json.dumps({
        "nbformat": nbformat,
        "nbformat_minor": nbformat_minor,
        "metadata": metadata or {},
        "cells": cells,
    })


class TestParseBasic(unittest.TestCase):
    def setUp(self):
        self.parser = NotebookParser()

    def test_parse_single_code_cell(self):
        raw = _make_nb_json()
        doc = self.parser.parse("nb.ipynb", read_fn=lambda p: raw)
        self.assertEqual(len(doc.cells), 1)
        self.assertEqual(doc.cells[0].cell_type, "code")
        self.assertEqual(doc.cells[0].source, "x = 1")

    def test_parse_preserves_nbformat(self):
        raw = _make_nb_json(nbformat=4, nbformat_minor=3)
        doc = self.parser.parse("nb.ipynb", read_fn=lambda p: raw)
        self.assertEqual(doc.nbformat, 4)
        self.assertEqual(doc.nbformat_minor, 3)

    def test_parse_preserves_metadata(self):
        raw = _make_nb_json(metadata={"kernelspec": {"name": "python3"}})
        doc = self.parser.parse("nb.ipynb", read_fn=lambda p: raw)
        self.assertIn("kernelspec", doc.metadata)

    def test_parse_multiple_cells(self):
        cells = [
            {"cell_type": "markdown", "source": "# Title", "metadata": {}},
            {"cell_type": "code", "source": "print(1)", "metadata": {}},
        ]
        raw = _make_nb_json(cells=cells)
        doc = self.parser.parse("nb.ipynb", read_fn=lambda p: raw)
        self.assertEqual(len(doc.cells), 2)
        self.assertEqual(doc.cells[0].cell_type, "markdown")

    def test_parse_cell_with_outputs(self):
        cells = [{
            "cell_type": "code",
            "source": "print('hi')",
            "metadata": {},
            "outputs": [{"output_type": "stream", "text": "hi\n"}],
            "execution_count": 1,
        }]
        raw = _make_nb_json(cells=cells)
        doc = self.parser.parse("nb.ipynb", read_fn=lambda p: raw)
        self.assertEqual(len(doc.cells[0].outputs), 1)
        self.assertEqual(doc.cells[0].outputs[0].output_type, "stream")
        self.assertEqual(doc.cells[0].outputs[0].text, "hi\n")
        self.assertEqual(doc.cells[0].execution_count, 1)

    def test_parse_source_as_list(self):
        cells = [{"cell_type": "code", "source": ["a = ", "1\n"], "metadata": {}}]
        raw = _make_nb_json(cells=cells)
        doc = self.parser.parse("nb.ipynb", read_fn=lambda p: raw)
        self.assertEqual(doc.cells[0].source, "a = 1\n")

    def test_parse_raw_cell(self):
        cells = [{"cell_type": "raw", "source": "raw text", "metadata": {}}]
        raw = _make_nb_json(cells=cells)
        doc = self.parser.parse("nb.ipynb", read_fn=lambda p: raw)
        self.assertEqual(doc.cells[0].cell_type, "raw")


class TestParseErrors(unittest.TestCase):
    def setUp(self):
        self.parser = NotebookParser()

    def test_invalid_json_raises(self):
        with self.assertRaises(NotebookParseError):
            self.parser.parse("nb.ipynb", read_fn=lambda p: "not json{{{")

    def test_missing_cells_raises(self):
        with self.assertRaises(NotebookParseError):
            self.parser.parse("nb.ipynb", read_fn=lambda p: '{"nbformat": 4}')

    def test_cells_not_list_raises(self):
        with self.assertRaises(NotebookParseError):
            self.parser.parse("nb.ipynb", read_fn=lambda p: '{"cells": "oops"}')

    def test_cell_not_dict_raises(self):
        with self.assertRaises(NotebookParseError):
            self.parser.parse("nb.ipynb", read_fn=lambda p: '{"cells": [42]}')

    def test_cell_missing_type_raises(self):
        with self.assertRaises(NotebookParseError):
            self.parser.parse("nb.ipynb", read_fn=lambda p: '{"cells": [{"source": "x"}]}')

    def test_read_fn_error_raises(self):
        def bad_read(p):
            raise OSError("disk error")
        with self.assertRaises(NotebookParseError):
            self.parser.parse("nb.ipynb", read_fn=bad_read)

    def test_root_not_dict_raises(self):
        with self.assertRaises(NotebookParseError):
            self.parser.from_dict([1, 2, 3])


class TestDump(unittest.TestCase):
    def setUp(self):
        self.parser = NotebookParser()

    def test_dump_roundtrip(self):
        doc = NotebookDoc(
            cells=[Cell(cell_type="code", source="x = 1")],
            metadata={"lang": "python"},
        )
        written = {}
        self.parser.dump(doc, "out.ipynb", write_fn=lambda p, c: written.update({p: c}))
        reloaded = self.parser.parse("out.ipynb", read_fn=lambda p: written[p])
        self.assertEqual(len(reloaded.cells), 1)
        self.assertEqual(reloaded.cells[0].source, "x = 1")

    def test_dump_to_disk(self):
        doc = NotebookDoc(cells=[Cell(cell_type="code", source="y = 2")])
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "test.ipynb")
        self.parser.dump(doc, path)
        reloaded = self.parser.parse(path)
        self.assertEqual(reloaded.cells[0].source, "y = 2")

    def test_dump_write_fn_called(self):
        doc = NotebookDoc(cells=[])
        calls = []
        self.parser.dump(doc, "p.ipynb", write_fn=lambda p, c: calls.append((p, c)))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "p.ipynb")


class TestToDict(unittest.TestCase):
    def setUp(self):
        self.parser = NotebookParser()

    def test_to_dict_structure(self):
        doc = NotebookDoc(cells=[Cell(cell_type="code", source="a")])
        d = self.parser.to_dict(doc)
        self.assertIn("cells", d)
        self.assertIn("nbformat", d)
        self.assertEqual(d["cells"][0]["cell_type"], "code")

    def test_to_dict_code_has_outputs_key(self):
        doc = NotebookDoc(cells=[Cell(cell_type="code", source="")])
        d = self.parser.to_dict(doc)
        self.assertIn("outputs", d["cells"][0])

    def test_to_dict_markdown_no_outputs(self):
        doc = NotebookDoc(cells=[Cell(cell_type="markdown", source="# H")])
        d = self.parser.to_dict(doc)
        self.assertNotIn("outputs", d["cells"][0])


class TestDiff(unittest.TestCase):
    def setUp(self):
        self.parser = NotebookParser()

    def test_identical_notebooks(self):
        doc = NotebookDoc(cells=[Cell(cell_type="code", source="x")])
        diff = self.parser.diff(doc, doc)
        self.assertEqual(diff.added, 0)
        self.assertEqual(diff.removed, 0)
        self.assertEqual(diff.changed, 0)

    def test_added_cell(self):
        doc1 = NotebookDoc(cells=[Cell(cell_type="code", source="x")])
        doc2 = NotebookDoc(cells=[Cell(cell_type="code", source="x"), Cell(cell_type="code", source="y")])
        diff = self.parser.diff(doc1, doc2)
        self.assertEqual(diff.added, 1)

    def test_removed_cell(self):
        doc1 = NotebookDoc(cells=[Cell(cell_type="code", source="x"), Cell(cell_type="code", source="y")])
        doc2 = NotebookDoc(cells=[Cell(cell_type="code", source="x")])
        diff = self.parser.diff(doc1, doc2)
        self.assertEqual(diff.removed, 1)

    def test_changed_cell(self):
        doc1 = NotebookDoc(cells=[Cell(cell_type="code", source="x")])
        doc2 = NotebookDoc(cells=[Cell(cell_type="code", source="y")])
        diff = self.parser.diff(doc1, doc2)
        self.assertEqual(diff.changed, 1)


class TestEmpty(unittest.TestCase):
    def test_empty_has_one_code_cell(self):
        parser = NotebookParser()
        doc = parser.empty()
        self.assertEqual(len(doc.cells), 1)
        self.assertEqual(doc.cells[0].cell_type, "code")
        self.assertEqual(doc.cells[0].source, "")

    def test_empty_nbformat(self):
        parser = NotebookParser()
        doc = parser.empty()
        self.assertEqual(doc.nbformat, 4)
        self.assertEqual(doc.nbformat_minor, 5)


if __name__ == "__main__":
    unittest.main()
