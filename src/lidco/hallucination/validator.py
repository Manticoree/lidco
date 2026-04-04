"""ReferenceValidator — validate file/function/line references in responses."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ReferenceCheck:
    """Result of validating a single reference."""

    reference: str
    ref_type: str  # "file", "function", "line", "snippet"
    valid: bool
    message: str = ""


class ReferenceValidator:
    """Validate that referenced files, functions, and line numbers exist."""

    def __init__(self, project_root: str = ".") -> None:
        self._root = project_root
        self._checks: list[ReferenceCheck] = []

    def validate_file(self, path: str) -> ReferenceCheck:
        """Check if a file path exists."""
        full = os.path.join(self._root, path)
        exists = os.path.isfile(full)
        check = ReferenceCheck(
            reference=path,
            ref_type="file",
            valid=exists,
            message="OK" if exists else f"File not found: {path}",
        )
        self._checks.append(check)
        return check

    def validate_line(self, path: str, line_num: int) -> ReferenceCheck:
        """Check if a line number exists in a file."""
        full = os.path.join(self._root, path)
        if not os.path.isfile(full):
            check = ReferenceCheck(
                reference=f"{path}:{line_num}",
                ref_type="line",
                valid=False,
                message=f"File not found: {path}",
            )
            self._checks.append(check)
            return check
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            valid = 1 <= line_num <= len(lines)
            check = ReferenceCheck(
                reference=f"{path}:{line_num}",
                ref_type="line",
                valid=valid,
                message="OK" if valid else f"Line {line_num} out of range (1-{len(lines)})",
            )
        except OSError as e:
            check = ReferenceCheck(
                reference=f"{path}:{line_num}",
                ref_type="line",
                valid=False,
                message=str(e),
            )
        self._checks.append(check)
        return check

    def validate_snippet(self, path: str, snippet: str) -> ReferenceCheck:
        """Check if a code snippet appears in a file."""
        full = os.path.join(self._root, path)
        if not os.path.isfile(full):
            check = ReferenceCheck(
                reference=f"snippet in {path}",
                ref_type="snippet",
                valid=False,
                message=f"File not found: {path}",
            )
            self._checks.append(check)
            return check
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                content = f.read()
            found = snippet.strip() in content
            check = ReferenceCheck(
                reference=f"snippet in {path}",
                ref_type="snippet",
                valid=found,
                message="OK" if found else "Snippet not found in file",
            )
        except OSError as e:
            check = ReferenceCheck(
                reference=f"snippet in {path}",
                ref_type="snippet",
                valid=False,
                message=str(e),
            )
        self._checks.append(check)
        return check

    def validate_function(self, path: str, func_name: str) -> ReferenceCheck:
        """Check if a function name is defined in a file."""
        full = os.path.join(self._root, path)
        if not os.path.isfile(full):
            check = ReferenceCheck(
                reference=f"{func_name} in {path}",
                ref_type="function",
                valid=False,
                message=f"File not found: {path}",
            )
            self._checks.append(check)
            return check
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                content = f.read()
            patterns = [f"def {func_name}(", f"def {func_name} (", f"async def {func_name}("]
            found = any(p in content for p in patterns)
            check = ReferenceCheck(
                reference=f"{func_name} in {path}",
                ref_type="function",
                valid=found,
                message="OK" if found else f"Function {func_name} not found",
            )
        except OSError as e:
            check = ReferenceCheck(
                reference=f"{func_name} in {path}",
                ref_type="function",
                valid=False,
                message=str(e),
            )
        self._checks.append(check)
        return check

    def checks(self) -> list[ReferenceCheck]:
        return list(self._checks)

    def validity_ratio(self) -> float:
        if not self._checks:
            return 0.0
        valid = sum(1 for c in self._checks if c.valid)
        return round(valid / len(self._checks), 3)

    def summary(self) -> dict:
        return {
            "total_checks": len(self._checks),
            "valid": sum(1 for c in self._checks if c.valid),
            "invalid": sum(1 for c in self._checks if not c.valid),
            "validity_ratio": self.validity_ratio(),
        }
