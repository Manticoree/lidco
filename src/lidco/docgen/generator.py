"""Docstring Generator — auto-generate docstrings from source code (stdlib only).

Parses Python functions/classes using the `ast` module and generates
Google-style, NumPy-style, or reStructuredText docstrings based on
signatures and type annotations.  Can inject docstrings back into source.
"""
from __future__ import annotations

import ast
import re
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocStyle(str, Enum):
    GOOGLE = "google"
    NUMPY = "numpy"
    RST = "rst"
    PLAIN = "plain"


class DocGenError(Exception):
    """Raised when docstring generation fails."""


@dataclass
class ParamInfo:
    name: str
    annotation: str = ""
    default: str = ""
    description: str = ""


@dataclass
class FunctionInfo:
    """Extracted metadata about a function or method."""

    name: str
    params: list[ParamInfo] = field(default_factory=list)
    return_annotation: str = ""
    existing_docstring: str = ""
    lineno: int = 0
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)

    def has_docstring(self) -> bool:
        return bool(self.existing_docstring.strip())

    def has_returns(self) -> bool:
        return bool(self.return_annotation and self.return_annotation not in ("None", "none"))


@dataclass
class ClassInfo:
    """Extracted metadata about a class."""

    name: str
    bases: list[str] = field(default_factory=list)
    methods: list[FunctionInfo] = field(default_factory=list)
    existing_docstring: str = ""
    lineno: int = 0

    def has_docstring(self) -> bool:
        return bool(self.existing_docstring.strip())


class DocGenerator:
    """Parse Python source and generate/inject docstrings.

    Usage::

        gen = DocGenerator(style=DocStyle.GOOGLE)
        source = 'def add(a: int, b: int) -> int:\\n    return a + b\\n'
        functions = gen.parse_functions(source)
        docstring = gen.generate_docstring(functions[0])
        new_source = gen.inject_docstring(source, functions[0], docstring)
    """

    def __init__(self, style: DocStyle = DocStyle.GOOGLE) -> None:
        self.style = style

    # ------------------------------------------------------------------ #
    # Parsing                                                              #
    # ------------------------------------------------------------------ #

    def parse_functions(self, source: str) -> list[FunctionInfo]:
        """Extract FunctionInfo list from Python source string."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise DocGenError(f"Syntax error in source: {exc}") from exc

        results: list[FunctionInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                results.append(self._extract_function(node))
        return results

    def parse_classes(self, source: str) -> list[ClassInfo]:
        """Extract ClassInfo list from Python source string."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise DocGenError(f"Syntax error in source: {exc}") from exc

        results: list[ClassInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                results.append(self._extract_class(node))
        return results

    def _extract_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> FunctionInfo:
        params: list[ParamInfo] = []
        args = node.args

        # defaults aligned to the end of args list
        n_args = len(args.args)
        n_defaults = len(args.defaults)
        defaults_start = n_args - n_defaults

        for i, arg in enumerate(args.args):
            if arg.arg == "self" or arg.arg == "cls":
                continue
            annotation = ast.unparse(arg.annotation) if arg.annotation else ""
            default = ""
            if i >= defaults_start:
                default = ast.unparse(args.defaults[i - defaults_start])
            params.append(ParamInfo(name=arg.arg, annotation=annotation, default=default))

        return_annotation = ""
        if node.returns:
            return_annotation = ast.unparse(node.returns)

        existing_doc = ""
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            existing_doc = node.body[0].value.value

        decorators = [ast.unparse(d) for d in node.decorator_list]

        return FunctionInfo(
            name=node.name,
            params=params,
            return_annotation=return_annotation,
            existing_docstring=existing_doc,
            lineno=node.lineno,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            decorators=decorators,
        )

    def _extract_class(self, node: ast.ClassDef) -> ClassInfo:
        bases = [ast.unparse(b) for b in node.bases]

        existing_doc = ""
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            existing_doc = node.body[0].value.value

        methods: list[FunctionInfo] = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._extract_function(item))

        return ClassInfo(
            name=node.name,
            bases=bases,
            methods=methods,
            existing_docstring=existing_doc,
            lineno=node.lineno,
        )

    # ------------------------------------------------------------------ #
    # Generation                                                           #
    # ------------------------------------------------------------------ #

    def generate_docstring(self, info: FunctionInfo | ClassInfo) -> str:
        """Generate a docstring for the given function or class info."""
        if self.style == DocStyle.GOOGLE:
            return self._google_docstring(info)
        if self.style == DocStyle.NUMPY:
            return self._numpy_docstring(info)
        if self.style == DocStyle.RST:
            return self._rst_docstring(info)
        return self._plain_docstring(info)

    def _google_docstring(self, info: FunctionInfo | ClassInfo) -> str:
        lines = [f"TODO: describe {info.name}."]
        if isinstance(info, FunctionInfo) and info.params:
            lines.append("")
            lines.append("Args:")
            for p in info.params:
                typ = f" ({p.annotation})" if p.annotation else ""
                default = f", defaults to {p.default}" if p.default else ""
                lines.append(f"    {p.name}{typ}: Description{default}.")
        if isinstance(info, FunctionInfo) and info.has_returns():
            lines.append("")
            lines.append("Returns:")
            lines.append(f"    {info.return_annotation}: Description.")
        return "\n".join(lines)

    def _numpy_docstring(self, info: FunctionInfo | ClassInfo) -> str:
        lines = [f"TODO: describe {info.name}.", ""]
        if isinstance(info, FunctionInfo) and info.params:
            lines += ["Parameters", "----------"]
            for p in info.params:
                typ = f" : {p.annotation}" if p.annotation else ""
                lines.append(f"{p.name}{typ}")
                lines.append("    Description.")
        if isinstance(info, FunctionInfo) and info.has_returns():
            lines += ["", "Returns", "-------"]
            lines.append(f"{info.return_annotation}")
            lines.append("    Description.")
        return "\n".join(lines)

    def _rst_docstring(self, info: FunctionInfo | ClassInfo) -> str:
        lines = [f"TODO: describe {info.name}."]
        if isinstance(info, FunctionInfo):
            lines.append("")
            for p in info.params:
                typ = f"\n:type {p.name}: {p.annotation}" if p.annotation else ""
                lines.append(f":param {p.name}: Description.{typ}")
            if info.has_returns():
                lines.append(f":returns: Description.")
                lines.append(f":rtype: {info.return_annotation}")
        return "\n".join(lines)

    def _plain_docstring(self, info: FunctionInfo | ClassInfo) -> str:
        name = info.name
        if isinstance(info, FunctionInfo) and info.params:
            param_names = ", ".join(p.name for p in info.params)
            return f"{name}({param_names}) — TODO: add description."
        return f"{name} — TODO: add description."

    # ------------------------------------------------------------------ #
    # Injection                                                            #
    # ------------------------------------------------------------------ #

    def inject_docstring(
        self,
        source: str,
        info: FunctionInfo | ClassInfo,
        docstring: str,
        indent: int = 4,
    ) -> str:
        """Return *source* with *docstring* injected after the def/class line."""
        lines = source.splitlines(keepends=True)
        lineno = info.lineno  # 1-based

        # Find the end of the def/class signature (handles multi-line signatures)
        insert_line = lineno  # 0-based index after def line
        for i in range(lineno - 1, min(lineno + 10, len(lines))):
            if lines[i].rstrip().endswith(":"):
                insert_line = i + 1
                break

        pad = " " * indent
        quoted = f'{pad}"""\n'
        for doc_line in docstring.splitlines():
            quoted += f"{pad}{doc_line}\n" if doc_line.strip() else f"\n"
        quoted += f'{pad}"""\n'

        lines.insert(insert_line, quoted)
        return "".join(lines)

    def needs_docstring(self, source: str) -> list[str]:
        """Return names of functions/classes missing docstrings."""
        missing: list[str] = []
        for fn in self.parse_functions(source):
            if not fn.has_docstring():
                missing.append(fn.name)
        for cls in self.parse_classes(source):
            if not cls.has_docstring():
                missing.append(cls.name)
        return missing
