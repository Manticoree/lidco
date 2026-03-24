"""Error explainer — parse tracebacks and suggest fixes (GitHub Copilot 'fix error' parity)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedError:
    error_type: str
    message: str
    file: str
    line: int
    traceback_frames: list[str]


@dataclass
class ErrorSuggestion:
    cause: str
    fix: str
    confidence: float   # 0.0–1.0


@dataclass
class ErrorExplanation:
    error: ParsedError
    suggestions: list[ErrorSuggestion]
    summary: str

    def format(self) -> str:
        lines = [
            f"Error: {self.error.error_type}: {self.error.message}",
            f"  in {self.error.file}:{self.error.line}",
            f"Summary: {self.summary}",
        ]
        for s in self.suggestions:
            lines.append(f"  [{s.confidence:.0%}] {s.cause} -> {s.fix}")
        return "\n".join(lines)


# Known error patterns → (error_type, pattern, cause, fix, confidence)
_ERROR_FIXES: list[tuple[str, str, str, str, float]] = [
    ("AttributeError", r"'NoneType' object has no attribute", "Variable is None unexpectedly", "Add a None check or return early", 0.9),
    ("AttributeError", r"has no attribute '(\w+)'", "Missing attribute or typo", "Check spelling and imports", 0.8),
    ("ImportError", r"No module named '(\w+)'", "Missing dependency", "Run `pip install <module>`", 0.95),
    ("ModuleNotFoundError", r"No module named", "Missing dependency", "Run `pip install <module>`", 0.95),
    ("TypeError", r"takes \d+ positional argument", "Wrong number of arguments", "Check function signature", 0.85),
    ("TypeError", r"unsupported operand type", "Type mismatch in operation", "Convert types before operation", 0.8),
    ("KeyError", r"", "Missing key in dict", "Use .get() with default or check key existence", 0.9),
    ("IndexError", r"list index out of range", "List access beyond bounds", "Check length before indexing", 0.9),
    ("FileNotFoundError", r"No such file", "File path does not exist", "Verify path with Path.exists()", 0.95),
    ("RecursionError", r"maximum recursion depth", "Infinite recursion", "Add a base case to stop recursion", 0.85),
    ("ValueError", r"invalid literal for int", "Non-numeric string passed to int()", "Validate input before conversion", 0.9),
    ("PermissionError", r"Permission denied", "Insufficient file permissions", "Check file permissions or run with sudo", 0.8),
    ("SyntaxError", r"", "Python syntax error", "Check indentation and syntax at indicated line", 0.95),
    ("AssertionError", r"", "Assertion failed in code or test", "Check the asserted condition and its inputs", 0.7),
]


def _parse_traceback(traceback_text: str) -> ParsedError:
    """Extract structured info from a Python traceback string."""
    lines = traceback_text.strip().splitlines()

    # Error type and message on last line
    error_type = "UnknownError"
    message = ""
    for line in reversed(lines):
        m = re.match(r"^(\w+(?:\.\w+)*Error|\w+Exception|\w+Error|\w+Warning): (.+)$", line.strip())
        if m:
            error_type = m.group(1)
            message = m.group(2)
            break
        if re.match(r"^\w+: .+$", line.strip()):
            parts = line.strip().split(": ", 1)
            error_type = parts[0]
            message = parts[1] if len(parts) > 1 else ""
            break

    # File and line from traceback frames
    file_path = ""
    line_no = 0
    frames: list[str] = []
    for ln in lines:
        m = re.search(r'File "([^"]+)", line (\d+)', ln)
        if m:
            file_path = m.group(1)
            line_no = int(m.group(2))
            frames.append(f"{file_path}:{line_no}")

    return ParsedError(
        error_type=error_type,
        message=message,
        file=file_path,
        line=line_no,
        traceback_frames=frames,
    )


class ErrorExplainer:
    """Parse Python tracebacks and suggest fixes."""

    def explain(self, traceback_text: str) -> ErrorExplanation:
        error = _parse_traceback(traceback_text)
        suggestions = self._suggest(error)
        summary = f"{error.error_type} at {error.file}:{error.line}" if error.file else f"{error.error_type}: {error.message[:80]}"
        return ErrorExplanation(error=error, suggestions=suggestions, summary=summary)

    def _suggest(self, error: ParsedError) -> list[ErrorSuggestion]:
        suggestions: list[ErrorSuggestion] = []
        for etype, pattern, cause, fix, conf in _ERROR_FIXES:
            if error.error_type == etype or etype in error.error_type:
                if not pattern or re.search(pattern, error.message, re.IGNORECASE):
                    suggestions.append(ErrorSuggestion(cause=cause, fix=fix, confidence=conf))
        return sorted(suggestions, key=lambda s: -s.confidence)[:3]

    def explain_text(self, text: str) -> str:
        """One-liner: parse traceback and return formatted explanation."""
        return self.explain(text).format()
