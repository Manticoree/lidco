"""TypeAnnotatorV2 — annotate Python functions and generate stubs (stdlib only)."""
from __future__ import annotations

import ast
import difflib
import re
import textwrap
from dataclasses import dataclass

from lidco.types.inferrer import InferredType


@dataclass(frozen=True)
class Annotation:
    """A single annotation change."""

    line: int
    original: str
    annotated: str


class TypeAnnotatorV2:
    """Annotate Python source with type hints."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def annotate_function(
        self,
        source: str,
        func_name: str,
        param_types: dict[str, str],
        return_type: str = "",
    ) -> str:
        """Return *source* with *func_name* annotated per *param_types* / *return_type*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        lines = source.splitlines(keepends=True)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name != func_name:
                continue
            lines = self._annotate_func_node(lines, node, param_types, return_type)
            break

        return "".join(lines)

    def annotate_all(self, source: str, inferred: list[InferredType]) -> str:
        """Annotate *source* using a list of *inferred* types (assignment + return)."""
        # Build lookup: func_name → return type, var_name → type
        return_types: dict[str, str] = {}
        var_types: dict[str, str] = {}
        for inf in inferred:
            if inf.source == "return":
                return_types[inf.name] = inf.type
            else:
                var_types[inf.name] = inf.type

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        lines = source.splitlines(keepends=True)

        # Annotate functions (return types only from inferred).
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            rt = return_types.get(node.name, "")
            if rt and node.returns is None:
                lines = self._annotate_func_node(lines, node, {}, rt)

        # Annotate variable assignments.
        result = "".join(lines)
        result = self._annotate_assignments(result, var_types)
        return result

    def generate_stub(self, source: str) -> str:
        """Generate a ``.pyi`` stub from *source*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ""

        parts: list[str] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                parts.append(ast.unparse(node))
            elif isinstance(node, ast.ImportFrom):
                parts.append(ast.unparse(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parts.append(self._stub_function(node))
            elif isinstance(node, ast.ClassDef):
                parts.append(self._stub_class(node))
            elif isinstance(node, ast.Assign):
                stub = self._stub_assignment(node)
                if stub:
                    parts.append(stub)

        return "\n".join(parts) + "\n" if parts else ""

    def diff(self, original: str, annotated: str) -> list[str]:
        """Return unified diff lines between *original* and *annotated*."""
        orig_lines = original.splitlines(keepends=True)
        ann_lines = annotated.splitlines(keepends=True)
        return list(
            difflib.unified_diff(orig_lines, ann_lines, fromfile="original", tofile="annotated")
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _annotate_func_node(
        lines: list[str],
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        param_types: dict[str, str],
        return_type: str,
    ) -> list[str]:
        """Return a new *lines* list with the function signature annotated."""
        # Locate the ``def`` line.
        idx = node.lineno - 1
        if idx >= len(lines):
            return list(lines)

        original_line = lines[idx]
        new_line = original_line

        # Annotate parameters.
        for pname, ptype in param_types.items():
            # Match bare parameter name (no existing annotation).
            pattern = rf'\b({re.escape(pname)})(\s*[,\):])'
            replacement = rf'\1: {ptype}\2'
            new_line = re.sub(pattern, replacement, new_line, count=1)

        # Annotate return type.
        if return_type and "->" not in new_line:
            new_line = re.sub(r'\)\s*:', f") -> {return_type}:", new_line, count=1)

        result = list(lines)
        result[idx] = new_line
        return result

    @staticmethod
    def _annotate_assignments(source: str, var_types: dict[str, str]) -> str:
        """Add type annotations to simple variable assignments."""
        lines = source.splitlines(keepends=True)
        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            annotated = False
            for vname, vtype in var_types.items():
                pattern = rf'^(\s*){re.escape(vname)}\s*=\s*'
                m = re.match(pattern, line)
                if m and ":" not in stripped.split("=")[0]:
                    indent = m.group(1)
                    rhs = line[m.end():]
                    result.append(f"{indent}{vname}: {vtype} = {rhs}")
                    annotated = True
                    break
            if not annotated:
                result.append(line)
        return "".join(result)

    def _stub_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Generate stub for a function."""
        params: list[str] = []
        for arg in node.args.args:
            name = arg.arg
            if arg.annotation:
                params.append(f"{name}: {ast.unparse(arg.annotation)}")
            else:
                params.append(name)

        ret = ""
        if node.returns:
            ret = f" -> {ast.unparse(node.returns)}"

        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(params)}){ret}: ..."

    def _stub_class(self, node: ast.ClassDef) -> str:
        """Generate stub for a class."""
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        header = f"class {node.name}({bases}):" if bases else f"class {node.name}:"
        members: list[str] = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                members.append("    " + self._stub_function(child))
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                ann = ast.unparse(child.annotation)
                members.append(f"    {child.target.id}: {ann}")
        if not members:
            members.append("    ...")
        return header + "\n" + "\n".join(members)

    @staticmethod
    def _stub_assignment(node: ast.Assign) -> str | None:
        """Generate stub for a module-level assignment."""
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if isinstance(node.value, ast.Constant):
                val = node.value.value
                if isinstance(val, bool):
                    return f"{name}: bool"
                if isinstance(val, int):
                    return f"{name}: int"
                if isinstance(val, float):
                    return f"{name}: float"
                if isinstance(val, str):
                    return f"{name}: str"
            return f"{name}: ..."
        return None
