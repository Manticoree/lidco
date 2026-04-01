"""Extract method/class/variable/constant from code."""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import Enum


class ExtractionType(str, Enum):
    """Kind of extraction."""

    METHOD = "method"
    CLASS = "class"
    VARIABLE = "variable"
    CONSTANT = "constant"


@dataclass(frozen=True)
class ExtractionResult:
    """Result of an extraction operation."""

    type: ExtractionType
    original: str
    extracted_name: str
    extracted_code: str
    remaining_code: str
    success: bool = True
    error: str = ""


class ExtractEngine:
    """Extract code fragments into named units."""

    def __init__(self) -> None:
        pass

    def extract_method(
        self, source: str, start_line: int, end_line: int, name: str
    ) -> ExtractionResult:
        """Extract lines *start_line*..*end_line* (1-based, inclusive) into a new function *name*."""
        lines = source.splitlines(keepends=True)
        if start_line < 1 or end_line > len(lines) or start_line > end_line:
            return ExtractionResult(
                type=ExtractionType.METHOD,
                original=source,
                extracted_name=name,
                extracted_code="",
                remaining_code=source,
                success=False,
                error=f"Invalid line range {start_line}-{end_line} (file has {len(lines)} lines).",
            )

        extracted_lines = lines[start_line - 1 : end_line]

        # Determine common indent of extracted block
        non_empty = [ln for ln in extracted_lines if ln.strip()]
        if non_empty:
            min_indent = min(len(ln) - len(ln.lstrip()) for ln in non_empty)
        else:
            min_indent = 0

        body_lines = []
        for ln in extracted_lines:
            if ln.strip():
                body_lines.append("    " + ln[min_indent:])
            else:
                body_lines.append("\n")

        extracted_code = f"def {name}():\n" + "".join(body_lines)
        if not extracted_code.endswith("\n"):
            extracted_code += "\n"

        # Build remaining code: replace extracted block with call
        indent = " " * min_indent
        call_line = f"{indent}{name}()\n"
        remaining = lines[: start_line - 1] + [call_line] + lines[end_line:]
        remaining_code = "".join(remaining)

        return ExtractionResult(
            type=ExtractionType.METHOD,
            original=source,
            extracted_name=name,
            extracted_code=extracted_code,
            remaining_code=remaining_code,
        )

    def extract_variable(
        self, source: str, expression: str, name: str
    ) -> ExtractionResult:
        """Replace first occurrence of *expression* with variable *name*."""
        if expression not in source:
            return ExtractionResult(
                type=ExtractionType.VARIABLE,
                original=source,
                extracted_name=name,
                extracted_code="",
                remaining_code=source,
                success=False,
                error=f"Expression '{expression}' not found in source.",
            )

        # Find the line containing the expression
        lines = source.splitlines(keepends=True)
        insert_idx = 0
        for i, ln in enumerate(lines):
            if expression in ln:
                insert_idx = i
                break

        # Determine indent of target line
        target_line = lines[insert_idx]
        indent = " " * (len(target_line) - len(target_line.lstrip()))

        assignment = f"{indent}{name} = {expression}\n"
        extracted_code = assignment

        # Replace first occurrence in source
        remaining_code = source.replace(expression, name, 1)
        # Insert assignment before the line that used the expression
        rem_lines = remaining_code.splitlines(keepends=True)
        # Find where replacement landed
        for i, ln in enumerate(rem_lines):
            if name in ln:
                rem_lines.insert(i, assignment)
                break
        remaining_code = "".join(rem_lines)

        return ExtractionResult(
            type=ExtractionType.VARIABLE,
            original=source,
            extracted_name=name,
            extracted_code=extracted_code,
            remaining_code=remaining_code,
        )

    def extract_constant(
        self, source: str, value: str, name: str
    ) -> ExtractionResult:
        """Replace literal *value* with constant *name* at module top."""
        if value not in source:
            return ExtractionResult(
                type=ExtractionType.CONSTANT,
                original=source,
                extracted_name=name,
                extracted_code="",
                remaining_code=source,
                success=False,
                error=f"Value '{value}' not found in source.",
            )

        assignment = f"{name} = {value}\n"
        remaining_code = source.replace(value, name)
        # Prepend constant definition
        remaining_code = assignment + remaining_code

        return ExtractionResult(
            type=ExtractionType.CONSTANT,
            original=source,
            extracted_name=name,
            extracted_code=assignment,
            remaining_code=remaining_code,
        )

    def preview(self, result: ExtractionResult) -> str:
        """Return a unified diff preview of the extraction."""
        if not result.success:
            return f"Error: {result.error}"
        orig = result.original.splitlines(keepends=True)
        new = result.remaining_code.splitlines(keepends=True)
        diff = difflib.unified_diff(orig, new, fromfile="before", tofile="after")
        return "".join(diff)
