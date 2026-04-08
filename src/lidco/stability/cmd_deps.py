"""
Command Dependency Checker.

Analyses handler source code for missing imports, unavailable dependencies,
and incorrect try/except import fallbacks.
"""
from __future__ import annotations

import importlib.util
import re


class CommandDependencyChecker:
    """Checks slash command handlers for import and dependency issues."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_dependencies(self, handler_source: str) -> list[dict]:
        """Check handler source code for missing imports/dependencies.

        Args:
            handler_source: Python source code of the handler function.

        Returns:
            List of dicts with "line", "dependency", "status"
            ("available"/"missing"), "suggestion".
        """
        findings: list[dict] = []
        lines = handler_source.splitlines()

        # Collect all import lines with their line numbers
        import_pattern = re.compile(
            r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))"
        )

        for lineno, text in enumerate(lines, start=1):
            match = import_pattern.match(text)
            if not match:
                continue
            module_name = match.group(1) or match.group(2).split(",")[0].strip()
            # Resolve to top-level package
            top_level = module_name.split(".")[0]
            available = importlib.util.find_spec(top_level) is not None
            status = "available" if available else "missing"
            suggestion = (
                ""
                if available
                else (
                    f"Install '{top_level}' or add a try/except import fallback. "
                    f"Example: try:\\n    import {top_level}\\nexcept ImportError:\\n"
                    f"    {top_level} = None"
                )
            )
            findings.append(
                {
                    "line": lineno,
                    "dependency": module_name,
                    "status": status,
                    "suggestion": suggestion,
                }
            )

        return findings

    def detect_missing_imports(self, source_code: str) -> list[dict]:
        """Find import statements that would fail at runtime.

        Args:
            source_code: Python source code (may be a full module).

        Returns:
            List of dicts with "line", "module", "available" (bool).
        """
        findings: list[dict] = []
        lines = source_code.splitlines()

        import_re = re.compile(
            r"^\s*(?:from\s+([\w.]+)\s+import\s+\S+|import\s+([\w.]+))"
        )

        for lineno, text in enumerate(lines, start=1):
            match = import_re.match(text)
            if not match:
                continue
            module_name = match.group(1) or match.group(2)
            top_level = module_name.split(".")[0]
            available = importlib.util.find_spec(top_level) is not None
            findings.append(
                {
                    "line": lineno,
                    "module": module_name,
                    "available": available,
                }
            )

        return findings

    def validate_fallbacks(self, source_code: str) -> list[dict]:
        """Check try/except import fallbacks are correct.

        Looks for patterns like:
            try:
                import foo
            except ImportError:
                foo = None

        Args:
            source_code: Python source code.

        Returns:
            List of dicts with "line", "module", "has_fallback" (bool),
            "fallback_correct" (bool).
        """
        findings: list[dict] = []
        lines = source_code.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i]
            # Look for "try:" blocks
            if re.match(r"^\s*try\s*:", line):
                try_line_idx = i
                # Scan ahead for an import inside the try block
                module_name: str | None = None
                import_lineno: int | None = None
                j = i + 1
                while j < len(lines) and not re.match(
                    r"^\s*except\b", lines[j]
                ):
                    m = re.match(
                        r"^\s*(?:from\s+([\w.]+)\s+import\s+\S+|import\s+([\w.]+))",
                        lines[j],
                    )
                    if m:
                        module_name = m.group(1) or m.group(2)
                        import_lineno = j + 1  # 1-based
                    j += 1

                if module_name is None:
                    i += 1
                    continue

                # Check for except ImportError / except (ImportError, …)
                has_fallback = False
                fallback_correct = False

                if j < len(lines) and re.match(
                    r"^\s*except\s+.*ImportError", lines[j]
                ):
                    has_fallback = True
                    # Check fallback body assigns None or similar
                    k = j + 1
                    while k < len(lines) and re.match(
                        r"^\s{4,}", lines[k]
                    ):
                        if re.search(r"=\s*None\b", lines[k]):
                            fallback_correct = True
                        k += 1

                findings.append(
                    {
                        "line": import_lineno or (try_line_idx + 1),
                        "module": module_name,
                        "has_fallback": has_fallback,
                        "fallback_correct": fallback_correct,
                    }
                )
                i = j + 1
                continue

            i += 1

        return findings

    def generate_report(self, findings: list[dict]) -> str:
        """Generate a text report from check_dependencies/detect_missing_imports findings.

        Args:
            findings: List of finding dicts.

        Returns:
            Multi-line text report string.
        """
        if not findings:
            return "No dependency issues found."

        lines: list[str] = ["Dependency Check Report", "=" * 40]
        for f in findings:
            # Support both check_dependencies and detect_missing_imports shapes
            if "status" in f:
                status = f["status"]
                dep = f.get("dependency", "")
                lineno = f.get("line", "?")
                suggestion = f.get("suggestion", "")
                marker = "[OK]" if status == "available" else "[MISSING]"
                lines.append(f"  Line {lineno}: {marker} {dep}")
                if suggestion:
                    lines.append(f"    Suggestion: {suggestion}")
            elif "available" in f:
                available = f["available"]
                module = f.get("module", "")
                lineno = f.get("line", "?")
                marker = "[OK]" if available else "[MISSING]"
                lines.append(f"  Line {lineno}: {marker} {module}")
            else:
                lines.append(f"  {f}")

        total = len(findings)
        missing = sum(
            1
            for f in findings
            if f.get("status") == "missing"
            or f.get("available") is False
        )
        lines.append("")
        lines.append(f"Total checked: {total}, Missing: {missing}")
        return "\n".join(lines)
