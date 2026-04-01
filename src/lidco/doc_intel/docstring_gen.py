"""Generate and update docstrings from function signatures."""
from __future__ import annotations

import ast
import enum
from dataclasses import dataclass, field


class DocStyle(str, enum.Enum):
    """Supported docstring styles."""

    GOOGLE = "google"
    NUMPY = "numpy"
    SPHINX = "sphinx"


@dataclass(frozen=True)
class GeneratedDocstring:
    """A generated docstring for a function."""

    function_name: str
    docstring: str
    style: DocStyle
    params: tuple[tuple[str, str], ...] = ()
    returns: str = ""


class DocstringGenerator:
    """Generate docstrings from Python source code."""

    def __init__(self, style: DocStyle = DocStyle.GOOGLE) -> None:
        self._style = style

    def set_style(self, style: DocStyle) -> None:
        """Change the active docstring style."""
        self._style = style

    def format_param(self, name: str, type_hint: str, description: str = "") -> str:
        """Format a single parameter line according to the current style."""
        desc = description or f"The {name} value."
        if self._style == DocStyle.GOOGLE:
            return f"    {name} ({type_hint}): {desc}"
        if self._style == DocStyle.NUMPY:
            return f"{name} : {type_hint}\n    {desc}"
        # SPHINX
        return f":param {name}: {desc}\n:type {name}: {type_hint}"

    def generate(self, source: str) -> GeneratedDocstring:
        """Parse a function definition and generate a docstring.

        Parses the first function found in *source*.
        """
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return self._gen_for_func(node)
        raise ValueError("No function definition found in source")

    def generate_for_class(self, source: str) -> list[GeneratedDocstring]:
        """Generate docstrings for all methods in the first class found."""
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                results: list[GeneratedDocstring] = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        results.append(self._gen_for_func(item))
                return results
        raise ValueError("No class definition found in source")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _gen_for_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> GeneratedDocstring:
        params = self._extract_params(node)
        returns = self._extract_return(node)
        docstring = self._build_docstring(node.name, params, returns)
        return GeneratedDocstring(
            function_name=node.name,
            docstring=docstring,
            style=self._style,
            params=params,
            returns=returns,
        )

    def _extract_params(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[tuple[str, str], ...]:
        result: list[tuple[str, str]] = []
        args = node.args
        for arg in args.args:
            if arg.arg == "self" or arg.arg == "cls":
                continue
            type_hint = ast.unparse(arg.annotation) if arg.annotation else "Any"
            result.append((arg.arg, type_hint))
        return tuple(result)

    def _extract_return(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        if node.returns is None:
            return ""
        return ast.unparse(node.returns)

    def _build_docstring(
        self,
        name: str,
        params: tuple[tuple[str, str], ...],
        returns: str,
    ) -> str:
        summary = f"{_humanize(name)}."
        if self._style == DocStyle.GOOGLE:
            return self._build_google(summary, params, returns)
        if self._style == DocStyle.NUMPY:
            return self._build_numpy(summary, params, returns)
        return self._build_sphinx(summary, params, returns)

    def _build_google(self, summary: str, params: tuple[tuple[str, str], ...], returns: str) -> str:
        lines = [summary]
        if params:
            lines.append("")
            lines.append("Args:")
            for pname, ptype in params:
                lines.append(f"    {pname} ({ptype}): The {pname} value.")
        if returns:
            lines.append("")
            lines.append("Returns:")
            lines.append(f"    {returns}: The result.")
        return "\n".join(lines)

    def _build_numpy(self, summary: str, params: tuple[tuple[str, str], ...], returns: str) -> str:
        lines = [summary]
        if params:
            lines.append("")
            lines.append("Parameters")
            lines.append("----------")
            for pname, ptype in params:
                lines.append(f"{pname} : {ptype}")
                lines.append(f"    The {pname} value.")
        if returns:
            lines.append("")
            lines.append("Returns")
            lines.append("-------")
            lines.append(f"{returns}")
            lines.append("    The result.")
        return "\n".join(lines)

    def _build_sphinx(self, summary: str, params: tuple[tuple[str, str], ...], returns: str) -> str:
        lines = [summary]
        if params:
            lines.append("")
            for pname, ptype in params:
                lines.append(f":param {pname}: The {pname} value.")
                lines.append(f":type {pname}: {ptype}")
        if returns:
            lines.append(f":returns: The result.")
            lines.append(f":rtype: {returns}")
        return "\n".join(lines)


def _humanize(name: str) -> str:
    """Convert a snake_case name to a human-readable summary."""
    words = name.replace("_", " ").strip()
    if words:
        words = words[0].upper() + words[1:]
    return words
