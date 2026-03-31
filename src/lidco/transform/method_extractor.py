"""AST-based method extraction — Q134 task 803."""
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from typing import List


@dataclass
class ExtractResult:
    method_name: str
    parameters: List[str] = field(default_factory=list)
    body: str = ""
    new_source: str = ""


class MethodExtractor:
    """Extract a range of lines into a new function."""

    def extract(
        self, source: str, start_line: int, end_line: int, method_name: str
    ) -> ExtractResult:
        """Extract lines [start_line, end_line] (1-based inclusive) into a new function."""
        lines = source.splitlines(True)
        if start_line < 1 or end_line < start_line or start_line > len(lines):
            return ExtractResult(method_name=method_name, new_source=source)

        end_line = min(end_line, len(lines))
        extracted_lines = lines[start_line - 1 : end_line]
        params = self.detect_parameters(source, start_line, end_line)

        # Determine indentation of the extracted block
        body_text = "".join(extracted_lines)
        dedented_body = textwrap.dedent(body_text)

        # Build the new function
        param_str = ", ".join(params)
        func_lines = [f"def {method_name}({param_str}):\n"]
        for bl in dedented_body.splitlines(True):
            func_lines.append("    " + bl if bl.strip() else bl)
        if not dedented_body.strip():
            func_lines.append("    pass\n")
        func_def = "".join(func_lines)

        # Build call expression
        call_expr_indent = ""
        if extracted_lines:
            first = extracted_lines[0]
            call_expr_indent = first[: len(first) - len(first.lstrip())]
        call_args = ", ".join(params)
        call_line = f"{call_expr_indent}{method_name}({call_args})\n"

        # Build new source: function def before the enclosing context, replace extracted lines with call
        new_lines = lines[: start_line - 1] + [call_line] + lines[end_line:]
        new_source = func_def + "\n" + "".join(new_lines)

        return ExtractResult(
            method_name=method_name,
            parameters=params,
            body=dedented_body,
            new_source=new_source,
        )

    def detect_parameters(
        self, source: str, start_line: int, end_line: int
    ) -> List[str]:
        """Find free variables in the line range that are used but not defined there."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        lines = source.splitlines()
        end_line = min(end_line, len(lines))

        defined_in_range: set[str] = set()
        used_in_range: set[str] = set()

        for node in ast.walk(tree):
            if not hasattr(node, "lineno"):
                continue
            if node.lineno < start_line or node.lineno > end_line:
                continue
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    defined_in_range.add(node.id)
                elif isinstance(node.ctx, (ast.Load, ast.Del)):
                    used_in_range.add(node.id)

        # Free variables = used but not defined in the range
        # Also exclude builtins
        import builtins

        builtin_names = set(dir(builtins))
        free = sorted(used_in_range - defined_in_range - builtin_names)
        return free

    def preview(
        self, source: str, start_line: int, end_line: int, method_name: str
    ) -> str:
        """Show what extracted function looks like without modifying source."""
        lines = source.splitlines(True)
        if start_line < 1 or end_line < start_line or start_line > len(lines):
            return ""

        end_line = min(end_line, len(lines))
        extracted_lines = lines[start_line - 1 : end_line]
        params = self.detect_parameters(source, start_line, end_line)

        body_text = "".join(extracted_lines)
        dedented_body = textwrap.dedent(body_text)

        param_str = ", ".join(params)
        func_lines = [f"def {method_name}({param_str}):\n"]
        for bl in dedented_body.splitlines(True):
            func_lines.append("    " + bl if bl.strip() else bl)
        if not dedented_body.strip():
            func_lines.append("    pass\n")
        return "".join(func_lines)
