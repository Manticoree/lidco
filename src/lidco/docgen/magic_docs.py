"""Magic Docs — auto-generate documentation from source code."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DocSection:
    """A single documentation section."""

    title: str
    content: str
    level: int


class MagicDocsGenerator:
    """Generate documentation sections from Python source files.

    Parses source code to extract signatures, docstrings, and usage
    examples, then produces structured documentation sections.
    """

    def generate(self, source_path: str) -> tuple[DocSection, ...]:
        """Generate doc sections from a Python source file path."""
        try:
            with open(source_path, "r", encoding="utf-8") as fh:
                code = fh.read()
        except (OSError, IOError):
            return ()
        return self._generate_from_code(code, source_path)

    def _generate_from_code(
        self, code: str, source_path: str
    ) -> tuple[DocSection, ...]:
        sections: list[DocSection] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return ()

        # Module docstring
        if (
            tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)
        ):
            sections.append(
                DocSection(
                    title="Module Overview",
                    content=tree.body[0].value.value.strip(),
                    level=1,
                )
            )

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or ""
                sections.append(
                    DocSection(title=f"Class: {node.name}", content=doc, level=2)
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node) or ""
                prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                sections.append(
                    DocSection(
                        title=f"Function: {prefix}{node.name}",
                        content=doc,
                        level=3,
                    )
                )
        return tuple(sections)

    def extract_signatures(self, code: str) -> tuple[str, ...]:
        """Extract function/method signatures from Python source."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return ()
        sigs: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                args_str = ast.unparse(node.args) if node.args else ""
                ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                sigs.append(f"{prefix}def {node.name}({args_str}){ret}")
        return tuple(sigs)

    def generate_examples(
        self, function_name: str, code: str
    ) -> tuple[str, ...]:
        """Generate simple usage examples for a function."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return ()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    params = [
                        a.arg
                        for a in node.args.args
                        if a.arg not in ("self", "cls")
                    ]
                    args_call = ", ".join(params)
                    example = f"{function_name}({args_call})"
                    return (example,)
        return ()

    def format_markdown(self, sections: tuple[DocSection, ...]) -> str:
        """Format doc sections as markdown."""
        lines: list[str] = []
        for section in sections:
            prefix = "#" * section.level
            lines.append(f"{prefix} {section.title}")
            lines.append("")
            if section.content:
                lines.append(section.content)
                lines.append("")
        return "\n".join(lines)


__all__ = ["DocSection", "MagicDocsGenerator"]
