"""Documentation Generator v2 — produce Markdown documentation from Python source (stdlib only).

Uses ``ast`` to extract module, class, and function metadata and renders
structured Markdown documentation with optional examples.
"""
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocSection:
    """A single section of generated documentation."""

    title: str
    content: str
    source_file: str = ""


class DocGeneratorV2:
    """Generate Markdown documentation from Python source code."""

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def generate_module(self, source: str, module_name: str) -> str:
        """Generate full module documentation.

        Produces a Markdown string with module docstring, classes, and functions.
        """
        tree = _parse(source)
        parts: list[str] = [f"# Module `{module_name}`", ""]

        module_doc = ast.get_docstring(tree)
        if module_doc:
            parts.append(module_doc)
            parts.append("")

        # Classes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                parts.append(self.generate_class(source, node.name))
                parts.append("")

        # Top-level functions
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parts.append(self.generate_function(source, node.name))
                parts.append("")

        return "\n".join(parts).rstrip() + "\n"

    def generate_function(self, source: str, func_name: str) -> str:
        """Generate documentation for a single function."""
        tree = _parse(source)
        node = _find_function(tree, func_name)
        if node is None:
            return f"Function `{func_name}` not found."

        sig = _build_signature(node)
        parts: list[str] = [f"## `{func_name}({sig})`", ""]

        doc = ast.get_docstring(node)
        if doc:
            parts.append(doc)
            parts.append("")

        params = _extract_params(node)
        if params:
            parts.append("**Parameters:**")
            parts.append("")
            for name, annotation in params:
                ann = f" (`{annotation}`)" if annotation else ""
                parts.append(f"- `{name}`{ann}")
            parts.append("")

        ret = _return_annotation(node)
        if ret:
            parts.append(f"**Returns:** `{ret}`")
            parts.append("")

        return "\n".join(parts).rstrip()

    def generate_class(self, source: str, class_name: str) -> str:
        """Generate documentation for a single class."""
        tree = _parse(source)
        node = _find_class(tree, class_name)
        if node is None:
            return f"Class `{class_name}` not found."

        bases = [ast.unparse(b) for b in node.bases]
        base_str = f"({', '.join(bases)})" if bases else ""
        parts: list[str] = [f"## Class `{class_name}{base_str}`", ""]

        doc = ast.get_docstring(node)
        if doc:
            parts.append(doc)
            parts.append("")

        methods = [
            n for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if methods:
            parts.append("**Methods:**")
            parts.append("")
            for m in methods:
                sig = _build_signature(m)
                mdoc = ast.get_docstring(m) or ""
                first_line = mdoc.split("\n")[0] if mdoc else "No description."
                parts.append(f"- `{m.name}({sig})` — {first_line}")
            parts.append("")

        return "\n".join(parts).rstrip()

    def add_examples(self, doc: str, examples: list[str]) -> str:
        """Append code examples to an existing doc string."""
        if not examples:
            return doc
        parts = [doc.rstrip(), "", "**Examples:**", ""]
        for ex in examples:
            parts.append("```python")
            parts.append(ex.strip())
            parts.append("```")
            parts.append("")
        return "\n".join(parts).rstrip()

    def to_markdown(self, sections: list[DocSection]) -> str:
        """Combine multiple *DocSection* instances into a single Markdown document."""
        parts: list[str] = []
        for sec in sections:
            parts.append(f"## {sec.title}")
            parts.append("")
            parts.append(sec.content)
            if sec.source_file:
                parts.append("")
                parts.append(f"*Source: {sec.source_file}*")
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #


def _parse(source: str) -> ast.Module:
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"Syntax error: {exc}") from exc


def _find_function(
    tree: ast.Module, name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _find_class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _build_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts: list[str] = []
    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        ann = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
        parts.append(f"{arg.arg}{ann}")
    return ", ".join(parts)


def _extract_params(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for arg in node.args.args:
        if arg.arg in ("self", "cls"):
            continue
        ann = ast.unparse(arg.annotation) if arg.annotation else ""
        result.append((arg.arg, ann))
    return result


def _return_annotation(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    if node.returns:
        return ast.unparse(node.returns)
    return ""
