"""Context compressor: keep signatures, drop bodies."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CompressedResult:
    """Result of context compression."""

    original_lines: int
    compressed_lines: int
    content: str
    ratio: float


class ContextCompressor:
    """Compresses code by keeping signatures/docstrings and dropping function bodies."""

    def compress(self, content: str, ratio: float = 0.5) -> CompressedResult:
        """Compress content by keeping structural elements and dropping bodies.

        Args:
            content: Source code text.
            ratio: Target compression ratio (0.0 = keep nothing, 1.0 = keep everything).
                   Default 0.5 means aim for ~50% of original lines.

        Returns:
            CompressedResult with compressed content and line counts.
        """
        if not content or not content.strip():
            return CompressedResult(
                original_lines=0,
                compressed_lines=0,
                content="",
                ratio=1.0,
            )

        lines = content.split("\n")
        original_count = len(lines)

        if ratio >= 1.0:
            return CompressedResult(
                original_lines=original_count,
                compressed_lines=original_count,
                content=content,
                ratio=1.0,
            )

        kept_lines = self._extract_structure(lines, ratio)
        compressed_content = "\n".join(kept_lines)
        compressed_count = len(kept_lines)

        actual_ratio = compressed_count / original_count if original_count > 0 else 1.0

        return CompressedResult(
            original_lines=original_count,
            compressed_lines=compressed_count,
            content=compressed_content,
            ratio=round(actual_ratio, 4),
        )

    def _extract_structure(self, lines: list[str], ratio: float) -> list[str]:
        """Extract structural elements from code lines."""
        kept: list[str] = []
        in_docstring = False
        docstring_delim: Optional[str] = None
        in_body = False
        body_indent = 0
        skip_body = False

        # Patterns for structural lines
        import_pat = re.compile(r"^\s*(import |from .+ import )")
        class_pat = re.compile(r"^\s*class\s+\w+")
        func_pat = re.compile(r"^\s*(async\s+)?def\s+\w+")
        decorator_pat = re.compile(r"^\s*@")
        comment_pat = re.compile(r"^\s*#")
        blank_pat = re.compile(r"^\s*$")
        assign_pat = re.compile(r"^\s*\w+\s*[:=]")
        docstring_start = re.compile(r'^\s*("""|\'\'\')')

        # First pass: identify all lines with their roles
        line_roles: list[str] = []  # "keep", "body", "blank"
        i = 0
        current_func_indent = -1

        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            # Track docstrings
            if in_docstring:
                line_roles.append("docstring")
                if docstring_delim and docstring_delim in stripped and i > 0:
                    # Check if this line closes the docstring
                    count = stripped.count(docstring_delim)
                    if count >= 1:
                        in_docstring = False
                        docstring_delim = None
                i += 1
                continue

            # Check for docstring start
            ds_match = docstring_start.match(line)
            if ds_match:
                delim = ds_match.group(1)
                # Single-line docstring
                rest_after_open = stripped[len(delim):]
                if delim in rest_after_open:
                    line_roles.append("docstring")
                    i += 1
                    continue
                else:
                    in_docstring = True
                    docstring_delim = delim
                    line_roles.append("docstring")
                    i += 1
                    continue

            if blank_pat.match(line):
                line_roles.append("blank")
            elif import_pat.match(line):
                line_roles.append("keep")
            elif decorator_pat.match(line):
                line_roles.append("keep")
            elif class_pat.match(line):
                line_roles.append("keep")
                current_func_indent = len(line) - len(line.lstrip())
            elif func_pat.match(line):
                line_roles.append("keep")
                current_func_indent = len(line) - len(line.lstrip())
            elif comment_pat.match(line):
                line_roles.append("comment")
            elif assign_pat.match(line) and (len(line) - len(line.lstrip())) == 0:
                # Top-level assignments
                line_roles.append("keep")
            else:
                line_roles.append("body")

            i += 1

        # Second pass: decide what to keep based on ratio
        # Always keep: structural lines, docstrings
        # Conditionally keep: blanks, comments, body lines
        for idx, role in enumerate(line_roles):
            if role in ("keep", "docstring"):
                kept.append(lines[idx])
            elif role == "blank":
                # Keep some blanks for readability
                if kept and kept[-1].strip() != "":
                    kept.append(lines[idx])
            elif role == "comment" and ratio >= 0.3:
                kept.append(lines[idx])
            elif role == "body":
                # For aggressive compression, replace body with ellipsis
                if ratio >= 0.7:
                    kept.append(lines[idx])
                elif kept and kept[-1].strip() != "...":
                    kept.append(_indent_of(lines[idx]) + "...")

        # Remove trailing blanks
        while kept and not kept[-1].strip():
            kept.pop()

        return kept


def _indent_of(line: str) -> str:
    """Extract the leading whitespace of a line."""
    return line[: len(line) - len(line.lstrip())]
