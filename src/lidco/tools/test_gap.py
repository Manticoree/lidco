"""Test gap analyzer — find functions/classes with no corresponding test."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult


class TestGapTool(BaseTool):
    """Find source symbols (functions/classes) that have no corresponding test."""

    @property
    def name(self) -> str:
        return "find_test_gaps"

    @property
    def description(self) -> str:
        return (
            "Identify functions and classes in source code that have no "
            "matching test. Uses the structural index when available, "
            "otherwise scans files directly."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path_prefix",
                type="string",
                description=(
                    "Restrict analysis to files under this path prefix "
                    "(e.g. 'src/lidco/core/'). Empty = entire src/."
                ),
                required=False,
                default="",
            ),
            ToolParameter(
                name="kind",
                type="string",
                description="Symbol kind to check: 'function', 'class', or 'all'.",
                required=False,
                default="all",
            ),
            ToolParameter(
                name="min_lines",
                type="integer",
                description="Minimum symbol body length (lines) to include in results.",
                required=False,
                default=3,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, **kwargs: Any) -> ToolResult:
        path_prefix: str = kwargs.get("path_prefix", "")
        kind: str = kwargs.get("kind", "all").lower()
        min_lines: int = int(kwargs.get("min_lines", 3))

        if kind not in ("function", "class", "all"):
            return ToolResult(
                output="", success=False,
                error="kind must be 'function', 'class', or 'all'."
            )

        cwd = Path.cwd()
        src_root = cwd / "src" if (cwd / "src").exists() else cwd

        # --- collect test names from test files ---
        test_names = _collect_test_names(cwd)

        # --- collect source symbols ---
        source_symbols = _collect_source_symbols(src_root, path_prefix, kind, min_lines)

        # --- find gaps ---
        gapped: list[dict[str, Any]] = []
        covered: list[dict[str, Any]] = []

        for sym in source_symbols:
            if _is_covered(sym["name"], test_names):
                covered.append(sym)
            else:
                gapped.append(sym)

        total = len(source_symbols)
        gap_count = len(gapped)
        cover_count = len(covered)
        pct = f"{100 * cover_count / total:.0f}%" if total else "N/A"

        lines: list[str] = [
            f"Test coverage gap analysis",
            f"Total symbols: {total} | Covered: {cover_count} ({pct}) | Gaps: {gap_count}\n",
        ]

        if not gapped:
            lines.append("All symbols appear to have corresponding tests.")
        else:
            lines.append(f"**{gap_count} untested symbol{'s' if gap_count != 1 else ''}:**\n")
            for sym in gapped[:50]:
                lines.append(
                    f"  {sym['kind']:8s} `{sym['name']}` — {sym['path']}:{sym['line']}"
                )
            if gap_count > 50:
                lines.append(f"  ... {gap_count - 50} more")

        return ToolResult(
            output="\n".join(lines),
            success=True,
            metadata={
                "total": total,
                "covered": cover_count,
                "gaps": gap_count,
                "gapped_symbols": [s["name"] for s in gapped[:20]],
            },
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_test_names(cwd: Path) -> set[str]:
    """Return normalised names of all test functions/methods found in test files."""
    names: set[str] = set()
    _test_func = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)", re.MULTILINE)
    _class_name = re.compile(r"^\s*class\s+(\w+)", re.MULTILINE)

    test_dirs = [
        p for p in [cwd / "tests", cwd / "test"]
        if p.exists()
    ]
    # Also catch test_*.py / *_test.py anywhere
    test_files = set()
    for td in test_dirs:
        test_files.update(td.rglob("*.py"))
    test_files.update(cwd.rglob("test_*.py"))
    test_files.update(cwd.rglob("*_test.py"))

    for tf in test_files:
        try:
            text = tf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in _test_func.finditer(text):
            names.add(m.group(1).lower())
        for m in _class_name.finditer(text):
            names.add(m.group(1).lower())

    return names


def _collect_source_symbols(
    src_root: Path,
    path_prefix: str,
    kind: str,
    min_lines: int,
) -> list[dict[str, Any]]:
    """Scan source files and return symbol dicts."""
    _func = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+(\w+)[ \t]*\(", re.MULTILINE)
    _cls = re.compile(r"^[ \t]*class[ \t]+(\w+)[ \t]*[:(]", re.MULTILINE)

    symbols: list[dict[str, Any]] = []
    py_files = list(src_root.rglob("*.py"))

    # Apply path prefix filter
    if path_prefix:
        norm = path_prefix.replace("\\", "/")
        py_files = [
            f for f in py_files
            if norm in str(f).replace("\\", "/")
        ]

    for pyf in py_files:
        try:
            text = pyf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()

        if kind in ("function", "all"):
            for m in _func.finditer(text):
                name = m.group(1)
                if name.startswith("__"):  # skip dunder
                    continue
                line_no = text.count("\n", 0, m.start()) + 1
                body_end = _estimate_body_end(lines, line_no - 1)
                if (body_end - line_no) < min_lines:
                    continue
                symbols.append({
                    "name": name,
                    "kind": "function",
                    "path": str(pyf.relative_to(src_root.parent) if src_root.parent != pyf else pyf),
                    "line": line_no,
                })

        if kind in ("class", "all"):
            for m in _cls.finditer(text):
                name = m.group(1)
                line_no = text.count("\n", 0, m.start()) + 1
                body_end = _estimate_body_end(lines, line_no - 1)
                if (body_end - line_no) < min_lines:
                    continue
                symbols.append({
                    "name": name,
                    "kind": "class",
                    "path": str(pyf.relative_to(src_root.parent) if src_root.parent != pyf else pyf),
                    "line": line_no,
                })

    return symbols


def _estimate_body_end(lines: list[str], start_idx: int) -> int:
    """Rough estimate of where the def/class body ends."""
    if start_idx >= len(lines):
        return start_idx
    base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    for i in range(start_idx + 1, min(start_idx + 200, len(lines))):
        line = lines[i]
        if line.strip() and len(line) - len(line.lstrip()) <= base_indent:
            return i
    return min(start_idx + 200, len(lines))


def _is_covered(symbol_name: str, test_names: set[str]) -> bool:
    """Heuristically check if a symbol has a corresponding test."""
    name_lower = symbol_name.lower()

    # Direct: test_symbol_name
    if f"test_{name_lower}" in test_names:
        return True

    # Class TestSymbol or TestSymbolName
    if f"test{name_lower}" in test_names:
        return True

    # Snake-case split: MyClass → my_class
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", symbol_name).lower()
    if f"test_{snake}" in test_names:
        return True
    if f"test{snake.replace('_', '')}" in test_names:
        return True

    # Partial containment in a test class name
    for tn in test_names:
        if name_lower in tn and tn.startswith("test"):
            return True

    return False
