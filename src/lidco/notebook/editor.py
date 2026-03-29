"""Notebook cell editor -- pure-functional operations on NotebookDoc."""

from __future__ import annotations

import copy
from dataclasses import replace

from lidco.notebook.parser import Cell, NotebookDoc


class NotebookEditError(Exception):
    pass


class NotebookEditor:
    """Immutable operations on NotebookDoc. All methods return a *new* doc."""

    def append_cell(self, doc: NotebookDoc, cell_type: str, source: str) -> NotebookDoc:
        """Return new NotebookDoc with a cell appended."""
        new_cell = Cell(cell_type=cell_type, source=source)
        return replace(doc, cells=[*doc.cells, new_cell])

    def replace_cell(self, doc: NotebookDoc, idx: int, source: str) -> NotebookDoc:
        """Return new NotebookDoc with cell at *idx* replaced."""
        self._validate_index(doc, idx)
        new_cells = list(doc.cells)
        old = new_cells[idx]
        new_cells[idx] = replace(old, source=source)
        return replace(doc, cells=new_cells)

    def delete_cell(self, doc: NotebookDoc, idx: int) -> NotebookDoc:
        """Return new NotebookDoc with cell at *idx* deleted."""
        self._validate_index(doc, idx)
        new_cells = [c for i, c in enumerate(doc.cells) if i != idx]
        return replace(doc, cells=new_cells)

    def move_cell(self, doc: NotebookDoc, from_idx: int, to_idx: int) -> NotebookDoc:
        """Return new NotebookDoc with cell moved from *from_idx* to *to_idx*."""
        self._validate_index(doc, from_idx)
        self._validate_index(doc, to_idx)
        new_cells = list(doc.cells)
        cell = new_cells.pop(from_idx)
        new_cells.insert(to_idx, cell)
        return replace(doc, cells=new_cells)

    def insert_cell(self, doc: NotebookDoc, idx: int, cell_type: str, source: str) -> NotebookDoc:
        """Insert a new cell at *idx* (before existing cell at that position)."""
        if idx < 0 or idx > len(doc.cells):
            raise NotebookEditError(f"Insert index {idx} out of range [0, {len(doc.cells)}]")
        new_cell = Cell(cell_type=cell_type, source=source)
        new_cells = list(doc.cells)
        new_cells.insert(idx, new_cell)
        return replace(doc, cells=new_cells)

    def clear_outputs(self, doc: NotebookDoc) -> NotebookDoc:
        """Return new NotebookDoc with all cell outputs cleared."""
        new_cells = [replace(c, outputs=[], execution_count=None) for c in doc.cells]
        return replace(doc, cells=new_cells)

    def apply_source_edit(self, doc: NotebookDoc, idx: int, new_source: str) -> NotebookDoc:
        """Alias for replace_cell -- used by SmartApply-style integration."""
        return self.replace_cell(doc, idx, new_source)

    @staticmethod
    def _validate_index(doc: NotebookDoc, idx: int) -> None:
        if idx < 0 or idx >= len(doc.cells):
            raise NotebookEditError(f"Cell index {idx} out of range [0, {len(doc.cells) - 1}]")
