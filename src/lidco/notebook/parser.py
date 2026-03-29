"""Jupyter notebook parser -- read/write .ipynb JSON as dataclass structures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Optional


@dataclass
class CellOutput:
    output_type: str  # "stream", "execute_result", "error"
    text: str = ""
    data: dict = field(default_factory=dict)


@dataclass
class Cell:
    cell_type: str  # "code", "markdown", "raw"
    source: str
    outputs: list[CellOutput] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    execution_count: Optional[int] = None


@dataclass
class NotebookDoc:
    cells: list[Cell]
    metadata: dict = field(default_factory=dict)
    nbformat: int = 4
    nbformat_minor: int = 5


@dataclass
class CellDiff:
    added: int
    removed: int
    changed: int


class NotebookParseError(Exception):
    pass


class NotebookParser:
    """Parse and serialize Jupyter .ipynb notebooks."""

    def parse(self, path: str, read_fn=None) -> NotebookDoc:
        """Read .ipynb JSON from *path* and return a NotebookDoc.

        If *read_fn* is provided it is called as ``read_fn(path) -> str``,
        otherwise the file is read from disk.

        Raises NotebookParseError for invalid JSON or missing required fields.
        """
        try:
            if read_fn is not None:
                raw = read_fn(path)
            else:
                with open(path, "r", encoding="utf-8") as fh:
                    raw = fh.read()
        except (OSError, TypeError) as exc:
            raise NotebookParseError(f"Cannot read notebook: {exc}") from exc

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise NotebookParseError(f"Invalid JSON: {exc}") from exc

        return self.from_dict(data)

    def dump(self, doc: NotebookDoc, path: str, write_fn=None) -> None:
        """Serialize *doc* to .ipynb JSON at *path*.

        Uses ``write_fn(path, content)`` if provided, else writes via ``open``.
        """
        content = json.dumps(self.to_dict(doc), indent=1, ensure_ascii=False)
        if write_fn is not None:
            write_fn(path, content)
        else:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)

    def to_dict(self, doc: NotebookDoc) -> dict:
        """Convert a NotebookDoc to a raw dict suitable for JSON serialization."""
        cells = []
        for cell in doc.cells:
            c: dict = {
                "cell_type": cell.cell_type,
                "source": cell.source,
                "metadata": dict(cell.metadata),
            }
            if cell.cell_type == "code":
                c["execution_count"] = cell.execution_count
                c["outputs"] = [
                    {
                        "output_type": o.output_type,
                        "text": o.text,
                        "data": dict(o.data),
                    }
                    for o in cell.outputs
                ]
            cells.append(c)
        return {
            "nbformat": doc.nbformat,
            "nbformat_minor": doc.nbformat_minor,
            "metadata": dict(doc.metadata),
            "cells": cells,
        }

    def from_dict(self, data: dict) -> NotebookDoc:
        """Parse a NotebookDoc from an already-loaded dict."""
        if not isinstance(data, dict):
            raise NotebookParseError("Notebook root must be a JSON object")
        if "cells" not in data:
            raise NotebookParseError("Missing required field: cells")

        raw_cells = data["cells"]
        if not isinstance(raw_cells, list):
            raise NotebookParseError("'cells' must be a list")

        cells: list[Cell] = []
        for idx, rc in enumerate(raw_cells):
            if not isinstance(rc, dict):
                raise NotebookParseError(f"Cell {idx} is not a JSON object")
            if "cell_type" not in rc:
                raise NotebookParseError(f"Cell {idx} missing 'cell_type'")

            outputs: list[CellOutput] = []
            for ro in rc.get("outputs", []):
                outputs.append(
                    CellOutput(
                        output_type=ro.get("output_type", "stream"),
                        text=ro.get("text", ""),
                        data=ro.get("data", {}),
                    )
                )

            source = rc.get("source", "")
            if isinstance(source, list):
                source = "".join(source)

            cells.append(
                Cell(
                    cell_type=rc["cell_type"],
                    source=source,
                    outputs=outputs,
                    metadata=rc.get("metadata", {}),
                    execution_count=rc.get("execution_count"),
                )
            )

        return NotebookDoc(
            cells=cells,
            metadata=data.get("metadata", {}),
            nbformat=data.get("nbformat", 4),
            nbformat_minor=data.get("nbformat_minor", 5),
        )

    def diff(self, doc1: NotebookDoc, doc2: NotebookDoc) -> CellDiff:
        """Compare two notebooks and return a CellDiff summary."""
        len1 = len(doc1.cells)
        len2 = len(doc2.cells)
        common = min(len1, len2)

        changed = 0
        for i in range(common):
            if doc1.cells[i].source != doc2.cells[i].source:
                changed += 1

        added = max(0, len2 - len1)
        removed = max(0, len1 - len2)
        return CellDiff(added=added, removed=removed, changed=changed)

    def empty(self) -> NotebookDoc:
        """Return an empty notebook with one empty code cell."""
        return NotebookDoc(
            cells=[Cell(cell_type="code", source="")],
            metadata={},
            nbformat=4,
            nbformat_minor=5,
        )
