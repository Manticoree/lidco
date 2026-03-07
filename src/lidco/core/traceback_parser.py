"""Structured traceback parser — extracts frames, locals, and root-cause hints."""

from __future__ import annotations

import linecache
import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Root-cause taxonomy
# ---------------------------------------------------------------------------

_ROOT_CAUSE_HINTS: dict[str, str] = {
    "AttributeError": "None object or missing attribute",
    "TypeError": "wrong argument type or None passed",
    "KeyError": "dictionary key not found",
    "ImportError": "missing module or circular import",
    "ModuleNotFoundError": "module not installed or wrong path",
    "NameError": "undefined variable or typo",
    "IndexError": "list index out of range",
    "ValueError": "invalid value or conversion failed",
    "OSError": "file/IO operation failed",
    "FileNotFoundError": "file does not exist",
    "PermissionError": "insufficient permissions",
    "RuntimeError": "runtime condition violated",
    "RecursionError": "infinite recursion detected",
    "StopIteration": "iterator exhausted unexpectedly",
    "AssertionError": "assertion failed in code",
    "SyntaxError": "Python syntax error",
    "IndentationError": "indentation error in code",
    "ZeroDivisionError": "division by zero",
}

# Regex to match frame header lines:
#   File "some/path.py", line 42, in some_function
_FRAME_RE = re.compile(
    r'File "([^"]+)",\s+line\s+(\d+),\s+in\s+(.+?)\s*\n\s*(.*)',
)

# Regex for local variable lines in --tb=long style:
#   varname = value
_LOCAL_VAR_RE = re.compile(r"^\s{4,}(\w+)\s*=\s*(.+)$")

# Regex for the trailing exception line: ExceptionType: message
_EXCEPTION_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*):\s*(.*)")

# Regex for bare exception with no message
_BARE_EXCEPTION_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)$")

# Words to skip when they look like exception types but are not
_NON_EXCEPTION_WORDS = frozenset({
    "Traceback",
    "During",
    "The",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TracebackFrame:
    """A single frame extracted from a Python traceback."""

    file: str        # absolute path (or "<built-in>" etc.)
    line: int        # line number
    function: str    # function name
    source: str      # source line text (from linecache or traceback text)
    locals_hint: str # "x=None, y=42" — first 3 local vars if available, else ""


@dataclass(frozen=True)
class ParsedTraceback:
    """Structured representation of a Python traceback."""

    error_type: str                        # "AttributeError"
    error_message: str                     # "object has no attribute 'foo'"
    frames: tuple[TracebackFrame, ...]     # full call stack
    failure_frame: TracebackFrame | None   # last frame (root failure site)
    root_cause_hint: str                   # taxonomy lookup result


# ---------------------------------------------------------------------------
# Parser implementation
# ---------------------------------------------------------------------------


def _is_builtin_file(path: str) -> bool:
    """Return True for synthetic file paths like '<string>' or '<frozen ...>'."""
    return path.startswith("<") and path.endswith(">")


def _get_source_line(file: str, line: int, fallback: str) -> str:
    """Retrieve the source line for *file*:*line* via linecache, or *fallback*."""
    if _is_builtin_file(file):
        return fallback.strip()
    try:
        cached = linecache.getline(file, line)
        if cached:
            return cached.rstrip()
    except Exception:  # noqa: BLE001
        pass
    return fallback.strip()


def _extract_exception_line(text: str) -> tuple[str, str]:
    """Scan *text* from the bottom up for a ``ExceptionType: message`` line.

    Returns (error_type, error_message) or ("UnknownError", "") when nothing
    is found.
    """
    lines = text.splitlines()
    for raw_line in reversed(lines):
        line = raw_line.strip()
        if not line:
            continue
        # Skip lines that look like frame headers or source lines
        if line.startswith("File "):
            continue
        if line.startswith("Traceback"):
            continue
        # Try "Type: message" first
        m = _EXCEPTION_LINE_RE.match(line)
        if m:
            exc_type = m.group(1)
            # Skip common non-exception words that happen to match the pattern
            if exc_type in _NON_EXCEPTION_WORDS:
                continue
            return exc_type, m.group(2)
        # Try bare exception name (e.g. just "StopIteration")
        m2 = _BARE_EXCEPTION_RE.match(line)
        if m2:
            exc_type = m2.group(1)
            if exc_type not in _NON_EXCEPTION_WORDS:
                return exc_type, ""
    return "UnknownError", ""


def _parse_locals_block(lines: list[str], start: int) -> tuple[str, int]:
    """Parse ``--tb=long`` style local-variable lines starting at *start*.

    Returns (locals_hint, next_index) where *next_index* is the first line
    not consumed.  At most 3 variables are included.
    """
    pairs: list[str] = []
    i = start
    while i < len(lines) and len(pairs) < 3:
        m = _LOCAL_VAR_RE.match(lines[i])
        if not m:
            break
        key = m.group(1)
        val = m.group(2).strip()
        # Truncate long values
        if len(val) > 40:
            val = val[:40] + "..."
        pairs.append(f"{key}={val}")
        i += 1
    return ", ".join(pairs), i


def parse_traceback(text: str) -> ParsedTraceback:
    """Parse a Python traceback string into a :class:`ParsedTraceback`.

    Supports standard tracebacks and ``--tb=long`` style output with local
    variable sections.  Handles built-in frames (``<string>``, ``<frozen …>``),
    and empty or malformed input.
    """
    if not text or not text.strip():
        return ParsedTraceback(
            error_type="UnknownError",
            error_message="",
            frames=(),
            failure_frame=None,
            root_cause_hint="",
        )

    # Split text into lines for locals parsing
    lines = text.splitlines()

    frames: list[TracebackFrame] = []

    # Find all frame positions using the regex
    for m in _FRAME_RE.finditer(text):
        file_path = m.group(1)
        line_no = int(m.group(2))
        function_name = m.group(3).strip()
        source_text_in_tb = m.group(4).strip()

        # Get actual source line (prefer linecache for real files)
        source = _get_source_line(file_path, line_no, source_text_in_tb)

        # Find which line index in `lines` follows the source text line
        # so we can look for locals after it.
        locals_hint = ""
        frame_end_pos = m.end()
        # Count newlines up to frame_end_pos to get the line index of the
        # source line itself, then add 1 to get the line after it.
        text_up_to_frame_end = text[:frame_end_pos]
        line_index_after_source = text_up_to_frame_end.count("\n") + 1

        if line_index_after_source < len(lines):
            locals_hint, _ = _parse_locals_block(lines, line_index_after_source)

        frames.append(
            TracebackFrame(
                file=file_path,
                line=line_no,
                function=function_name,
                source=source,
                locals_hint=locals_hint,
            )
        )

    error_type, error_message = _extract_exception_line(text)
    frames_tuple = tuple(frames)
    failure_frame = frames_tuple[-1] if frames_tuple else None
    root_cause_hint = _ROOT_CAUSE_HINTS.get(error_type, "")

    return ParsedTraceback(
        error_type=error_type,
        error_message=error_message,
        frames=frames_tuple,
        failure_frame=failure_frame,
        root_cause_hint=root_cause_hint,
    )
