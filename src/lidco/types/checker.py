"""TypeCheckerIntegration — parse mypy/pyright output and suggest fixes (stdlib only)."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckError:
    """A single type-checker error."""

    file: str
    line: int
    message: str
    severity: str = "error"
    code: str = ""


# mypy line:  path/to/file.py:10: error: Incompatible types ... [assignment]
_MYPY_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):\s*(?P<sev>error|warning|note):\s*(?P<msg>.+?)(?:\s*\[(?P<code>[^\]]+)\])?\s*$"
)

# pyright line:  path/to/file.py:10:5 - error: Cannot assign ... (reportGeneralClassIssues)
_PYRIGHT_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):\d+\s*-\s*(?P<sev>error|warning|information):\s*(?P<msg>.+?)(?:\s*\((?P<code>[^\)]+)\))?\s*$"
)

# Fix suggestions keyed by substring in the error message.
_FIX_HINTS: list[tuple[str, str]] = [
    ("Incompatible return value type", 'Update the return type annotation or fix the returned value.'),
    ("Incompatible types in assignment", 'Change the variable annotation or the assigned value.'),
    ('is not assignable to type', 'Ensure the value matches the declared type.'),
    ("Missing return statement", 'Add a return statement or annotate return type as None.'),
    ("has no attribute", 'Check the object type — the attribute may not exist on it.'),
    ("Cannot assign", 'Verify the type annotation matches the assigned value.'),
    ("Argument of type", 'Cast the argument or change the parameter type.'),
    ('expected', 'Ensure the argument matches the expected type.'),
    ('override', 'Match the parent method signature in the override.'),
    ('import', 'Verify the module exists and is installed.'),
    ('unresolved', 'Check spelling and ensure the symbol is exported.'),
    ('unused', 'Remove the unused import or variable, or prefix with underscore.'),
    ('possibly unbound', 'Initialize the variable before use in all code paths.'),
    ('could be None', 'Add a None check before accessing the value.'),
    ('not callable', 'Verify the object is callable (function, class, or has __call__).'),
]


class TypeCheckerIntegration:
    """Parse type-checker output and provide fix suggestions."""

    def parse_mypy_output(self, output: str) -> list[CheckError]:
        """Parse mypy text output into :class:`CheckError` objects."""
        errors: list[CheckError] = []
        for line in output.splitlines():
            m = _MYPY_RE.match(line.strip())
            if m:
                errors.append(
                    CheckError(
                        file=m.group("file"),
                        line=int(m.group("line")),
                        message=m.group("msg").strip(),
                        severity=m.group("sev"),
                        code=m.group("code") or "",
                    )
                )
        return errors

    def parse_pyright_output(self, output: str) -> list[CheckError]:
        """Parse pyright text output into :class:`CheckError` objects."""
        errors: list[CheckError] = []
        for line in output.splitlines():
            m = _PYRIGHT_RE.match(line.strip())
            if m:
                sev = m.group("sev")
                if sev == "information":
                    sev = "note"
                errors.append(
                    CheckError(
                        file=m.group("file"),
                        line=int(m.group("line")),
                        message=m.group("msg").strip(),
                        severity=sev,
                        code=m.group("code") or "",
                    )
                )
        return errors

    def suggest_fix(self, error: CheckError) -> str | None:
        """Return a human-readable fix suggestion for *error*, or ``None``."""
        msg_lower = error.message.lower()
        for pattern, suggestion in _FIX_HINTS:
            if pattern.lower() in msg_lower:
                return suggestion
        return None

    def summary(self, errors: list[CheckError]) -> str:
        """Return a short summary string for a list of errors."""
        if not errors:
            return "No type errors found."
        by_sev: dict[str, int] = {}
        for e in errors:
            by_sev[e.severity] = by_sev.get(e.severity, 0) + 1
        parts = [f"{count} {sev}(s)" for sev, count in sorted(by_sev.items())]
        total = len(errors)
        files = len({e.file for e in errors})
        return f"{total} issue(s) in {files} file(s): {', '.join(parts)}."
