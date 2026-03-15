"""Inline code actions for LIDCO — Task 436.

Analyses a line of source code and suggests applicable AI actions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CodeAction:
    """A suggested inline code action.

    Attributes:
        title: Human-readable action label.
        kind: Category, e.g. ``"refactor"``, ``"quickfix"``, ``"generate"``.
        file: Source file path (may be empty string if not applicable).
        line: 1-based line number.
        command_hint: Suggested LIDCO prompt to run this action.
    """

    title: str
    kind: str
    file: str
    line: int
    command_hint: str


# ---------------------------------------------------------------------------
# Pattern matchers
# ---------------------------------------------------------------------------

_RAISE_EXCEPTION_RE = re.compile(r"\braise\s+Exception\s*\(")
_TODO_RE = re.compile(r"#\s*TODO\b", re.IGNORECASE)
_FIXME_RE = re.compile(r"#\s*FIXME\b", re.IGNORECASE)
_FUNC_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+\w+")
_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+\S")
_BARE_EXCEPT_RE = re.compile(r"^\s*except\s*:")


def _make_action(
    title: str,
    kind: str,
    file: str,
    line: int,
    command_hint: str,
) -> CodeAction:
    return CodeAction(
        title=title,
        kind=kind,
        file=file,
        line=line,
        command_hint=command_hint,
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class CodeActionProvider:
    """Produces a list of applicable code actions for a given file and line.

    Usage::

        provider = CodeActionProvider()
        actions = provider.get_actions("src/foo.py", 42)
    """

    def get_actions(self, file_path: str, line: int) -> list[CodeAction]:
        """Return code actions for *line* (1-based) in *file_path*.

        If the file cannot be read or *line* is out of range an empty list
        is returned.
        """
        line_text = self._read_line(file_path, line)
        if line_text is None:
            return []
        return self._analyse(line_text, file_path, line)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _read_line(self, file_path: str, line: int) -> str | None:
        """Return the text of 1-based *line* from *file_path*, or None."""
        try:
            lines = Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return None
        if line < 1 or line > len(lines):
            return None
        return lines[line - 1]

    def _analyse(self, line_text: str, file_path: str, line: int) -> list[CodeAction]:
        """Return actions appropriate for *line_text*."""
        actions: list[CodeAction] = []
        fp = file_path

        # 1. bare `raise Exception(...)` → convert to custom exception
        if _RAISE_EXCEPTION_RE.search(line_text):
            actions.append(_make_action(
                title="Convert to custom exception",
                kind="refactor",
                file=fp,
                line=line,
                command_hint=f"Convert the generic Exception on line {line} in {fp} to a custom exception class.",
            ))

        # 2. TODO comment → implement
        if _TODO_RE.search(line_text):
            actions.append(_make_action(
                title="Ask AI to implement TODO",
                kind="generate",
                file=fp,
                line=line,
                command_hint=f"Implement the TODO comment on line {line} in {fp}.",
            ))

        # 3. FIXME comment → fix
        if _FIXME_RE.search(line_text):
            actions.append(_make_action(
                title="Ask AI to fix FIXME",
                kind="quickfix",
                file=fp,
                line=line,
                command_hint=f"Fix the issue marked FIXME on line {line} in {fp}.",
            ))

        # 4. Function definition → generate docstring + tests
        if _FUNC_DEF_RE.match(line_text):
            actions.append(_make_action(
                title="Generate docstring",
                kind="generate",
                file=fp,
                line=line,
                command_hint=f"Generate a docstring for the function defined on line {line} in {fp}.",
            ))
            actions.append(_make_action(
                title="Generate tests",
                kind="generate",
                file=fp,
                line=line,
                command_hint=f"Generate pytest tests for the function defined on line {line} in {fp}.",
            ))

        # 5. Import line with potential error marker → fix import
        if _IMPORT_RE.match(line_text):
            actions.append(_make_action(
                title="Fix import",
                kind="quickfix",
                file=fp,
                line=line,
                command_hint=f"Fix the import statement on line {line} in {fp}.",
            ))

        # 6. Bare except → add specific exception type
        if _BARE_EXCEPT_RE.match(line_text):
            actions.append(_make_action(
                title="Add specific exception type",
                kind="refactor",
                file=fp,
                line=line,
                command_hint=f"Replace the bare except on line {line} in {fp} with a specific exception type.",
            ))

        return actions
