"""Human-readable reporting and auto-fix for validation results."""
from __future__ import annotations

from typing import Any

from lidco.conversation.validator import ValidationResult


class ValidationReporter:
    """Report on validation results and optionally auto-fix messages.

    Modes
    -----
    ``"strict"``  — report only, never fix.
    ``"lenient"`` — attempt automatic fixes and report what was changed.
    """

    def __init__(self, *, mode: str = "strict") -> None:
        self._mode = mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        """Set mode to ``'strict'`` or ``'lenient'``."""
        if mode not in ("strict", "lenient"):
            raise ValueError(f"Invalid mode '{mode}'. Must be 'strict' or 'lenient'.")
        self._mode = mode

    @property
    def mode(self) -> str:
        return self._mode

    def report(self, results: list[ValidationResult]) -> str:
        """Return a human-readable multi-line report of *results*."""
        lines: list[str] = []
        for idx, res in enumerate(results):
            status = "PASS" if res.is_valid else "FAIL"
            lines.append(f"Message {idx}: {status}")
            for err in res.errors:
                lines.append(f"  - {err}")
        stats = self.summary(results)
        lines.append("")
        lines.append(
            f"Total: {stats['total']}  Valid: {stats['valid']}  Invalid: {stats['invalid']}"
        )
        return "\n".join(lines)

    def summary(self, results: list[ValidationResult]) -> dict[str, int]:
        """Return counts dict with ``total``, ``valid``, ``invalid``."""
        valid = sum(1 for r in results if r.is_valid)
        return {
            "total": len(results),
            "valid": valid,
            "invalid": len(results) - valid,
        }

    def auto_fix(self, message: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Attempt to fix common issues in *message*.

        Returns a **(fixed_message, fixes_applied)** tuple.  The original
        dict is never mutated.
        """
        fixed: dict[str, Any] = dict(message)
        fixes: list[str] = []

        # Fix missing role
        if "role" not in fixed:
            fixed = {**fixed, "role": "user"}
            fixes.append("Added default role 'user'.")

        # Fix string content → wrap in blocks
        content = fixed.get("content")
        if isinstance(content, str):
            fixed = {
                **fixed,
                "content": [{"type": "text", "text": content}],
            }
            fixes.append("Wrapped string content in content block list.")

        # Fix missing tool_call_id for tool role
        if fixed.get("role") == "tool" and "tool_call_id" not in fixed:
            fixed = {**fixed, "tool_call_id": "placeholder"}
            fixes.append("Added placeholder tool_call_id.")

        return fixed, fixes
