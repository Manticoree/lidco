"""Notebook agent -- natural-language-driven cell operations."""

from __future__ import annotations

import re
from typing import Optional

from lidco.notebook.editor import NotebookEditor
from lidco.notebook.parser import Cell, NotebookDoc


class NotebookAgent:
    """Execute natural-language instructions on a NotebookDoc."""

    def __init__(self, editor: Optional[NotebookEditor] = None, planning_agent=None):
        self._editor = editor or NotebookEditor()
        self._planning_agent = planning_agent

    def execute_plan(self, instruction: str, doc: NotebookDoc, llm_fn=None) -> NotebookDoc:
        """Parse *instruction* and apply cell operations heuristically.

        If *llm_fn* is provided it can be used for advanced NL parsing;
        otherwise simple keyword heuristics are used.
        """
        text = instruction.strip().lower()

        if text in ("clear outputs", "clear all outputs"):
            return self._editor.clear_outputs(doc)

        # "delete cell N"
        m = re.match(r"delete\s+cell\s+(\d+)", text)
        if m:
            idx = int(m.group(1)) - 1
            return self._editor.delete_cell(doc, idx)

        # "fix cell N"
        m = re.match(r"fix\s+cell\s+(\d+)", text)
        if m:
            idx = int(m.group(1)) - 1
            old_source = doc.cells[idx].source if 0 <= idx < len(doc.cells) else ""
            return self._editor.replace_cell(doc, idx, f"# fixed\n{old_source}")

        # "add markdown ..."
        if text.startswith("add markdown"):
            content = instruction.strip()[len("add markdown"):].strip()
            return self._editor.append_cell(doc, "markdown", content or "# Markdown cell")

        # "add code cell" / "add a cell" / "add cell"
        if re.match(r"add\s+(a\s+)?(code\s+)?cell", text):
            return self._editor.append_cell(doc, "code", "# new cell")

        # Fallback: append markdown cell with the instruction as source
        return self._editor.append_cell(doc, "markdown", instruction.strip())

    def analyze(self, doc: NotebookDoc) -> dict:
        """Return a summary analysis of the notebook."""
        code_cells = sum(1 for c in doc.cells if c.cell_type == "code")
        md_cells = sum(1 for c in doc.cells if c.cell_type == "markdown")
        has_outputs = any(bool(c.outputs) for c in doc.cells)

        summaries: list[str] = []
        for i, c in enumerate(doc.cells):
            preview = c.source[:60].replace("\n", " ")
            summaries.append(f"[{i}] {c.cell_type}: {preview}")

        return {
            "total_cells": len(doc.cells),
            "code_cells": code_cells,
            "markdown_cells": md_cells,
            "has_outputs": has_outputs,
            "cell_summary": summaries,
        }
