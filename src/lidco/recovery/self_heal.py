"""Self-healing engine for common code errors."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HealResult:
    """Outcome of a self-heal attempt."""

    error_type: str
    fix_applied: str
    original: str
    fixed: str
    success: bool


class SelfHealEngine:
    """Auto-fix common errors: missing imports, syntax, indentation."""

    def __init__(self) -> None:
        self._history: list[HealResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def heal(self, error_message: str, code: str = "") -> HealResult | None:
        """Attempt to auto-fix *error_message* against *code*."""
        msg = error_message.lower()

        # Missing import ---------------------------------------------------
        m = re.search(
            r"(?:modulenotfounderror|importerror).*?['\"](\w+)['\"]",
            error_message,
            re.IGNORECASE,
        )
        if m:
            module = m.group(1)
            fixed = self.fix_missing_import(code, module)
            result = HealResult(
                error_type="import",
                fix_applied=f"Added import {module}",
                original=code,
                fixed=fixed,
                success=fixed != code,
            )
            self._history.append(result)
            return result

        # Syntax: missing colon -------------------------------------------
        if "expected ':'" in msg or ("syntaxerror" in msg and ":" in msg):
            m2 = re.search(r"line (\d+)", error_message, re.IGNORECASE)
            line = int(m2.group(1)) if m2 else 0
            if code and line > 0:
                fixed = self.fix_syntax_error(code, line)
                result = HealResult(
                    error_type="syntax",
                    fix_applied=f"Fixed syntax at line {line}",
                    original=code,
                    fixed=fixed,
                    success=fixed != code,
                )
                self._history.append(result)
                return result

        # Indentation ------------------------------------------------------
        if "indentationerror" in msg or "unexpected indent" in msg:
            if code:
                fixed = self.fix_indentation(code)
                result = HealResult(
                    error_type="indentation",
                    fix_applied="Normalized indentation",
                    original=code,
                    fixed=fixed,
                    success=fixed != code,
                )
                self._history.append(result)
                return result

        return None

    def fix_missing_import(self, code: str, module_name: str) -> str:
        """Prepend ``import <module_name>`` if not already present."""
        import_line = f"import {module_name}"
        if import_line in code:
            return code
        lines = code.split("\n")
        # Insert after any existing imports / from __future__
        insert_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                insert_idx = i + 1
        lines.insert(insert_idx, import_line)
        return "\n".join(lines)

    def fix_syntax_error(
        self, code: str, line: int, suggestion: str = ""
    ) -> str:
        """Basic syntax fixes at *line* (1-based): missing colon, unmatched paren."""
        lines = code.split("\n")
        if line < 1 or line > len(lines):
            return code
        idx = line - 1
        target = lines[idx]

        # Missing colon after def/class/if/elif/else/for/while/with/try/except/finally
        kw_pat = re.compile(
            r"^(\s*(?:def|class|if|elif|else|for|while|with|try|except|finally)\b.*)$"
        )
        m = kw_pat.match(target)
        if m and not target.rstrip().endswith(":"):
            lines[idx] = target.rstrip() + ":"
            return "\n".join(lines)

        # Unmatched opening paren — append closing
        if target.count("(") > target.count(")"):
            lines[idx] = target.rstrip() + ")"
            return "\n".join(lines)

        # If a suggestion is given, append as comment
        if suggestion:
            lines[idx] = target + f"  # suggestion: {suggestion}"
            return "\n".join(lines)

        return code

    def fix_indentation(self, code: str) -> str:
        """Normalize indentation to 4-space multiples."""
        lines = code.split("\n")
        result: list[str] = []
        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                result.append("")
                continue
            raw_indent = len(line) - len(stripped)
            # Round to nearest multiple of 4
            level = round(raw_indent / 4)
            result.append("    " * level + stripped)
        return "\n".join(result)

    def preview(self, error_message: str, code: str = "") -> str:
        """Show what would change without recording in history."""
        result = self.heal(error_message, code)
        if result is None:
            return "No auto-fix available."
        # Remove from history since this is a preview
        if self._history and self._history[-1] is result:
            self._history.pop()
        if result.original == result.fixed:
            return "No changes needed."
        return f"Fix: {result.fix_applied}\n--- original ---\n{result.original}\n--- fixed ---\n{result.fixed}"

    def history(self) -> list[HealResult]:
        """Return all past heal results."""
        return list(self._history)

    def success_rate(self) -> float:
        """Return success ratio (0.0 if no history)."""
        if not self._history:
            return 0.0
        successes = sum(1 for r in self._history if r.success)
        return successes / len(self._history)

    def summary(self) -> dict:
        """Return summary statistics."""
        return {
            "total_heals": len(self._history),
            "successes": sum(1 for r in self._history if r.success),
            "success_rate": self.success_rate(),
        }
