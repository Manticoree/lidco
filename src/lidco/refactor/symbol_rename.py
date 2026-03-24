# src/lidco/refactor/symbol_rename.py
"""Cross-file symbol rename — finds and replaces identifier occurrences."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RenameOccurrence:
    file: str
    line: int
    column: int
    context: str  # the full line text


@dataclass
class RenameResult:
    old_name: str
    new_name: str
    files_changed: int
    occurrences: int
    preview: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SymbolRenamer:
    """Rename a symbol (variable, function, class) across all Python files in a directory."""

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()

    def _iter_py_files(self) -> list[Path]:
        """Return all .py files under root, excluding common noise dirs."""
        skip = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox"}
        result = []
        for p in self.root.rglob("*.py"):
            if not any(part in skip for part in p.parts):
                result.append(p)
        return result

    def find_occurrences(self, name: str) -> list[RenameOccurrence]:
        """Return all occurrences of identifier `name` as whole-word matches."""
        pattern = re.compile(r"\b" + re.escape(name) + r"\b")
        occurrences: list[RenameOccurrence] = []
        for path in self._iter_py_files():
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                for m in pattern.finditer(line):
                    occurrences.append(RenameOccurrence(
                        file=str(path),
                        line=lineno,
                        column=m.start(),
                        context=line,
                    ))
        return occurrences

    def rename(
        self,
        old_name: str,
        new_name: str,
        *,
        dry_run: bool = False,
        extensions: list[str] | None = None,
    ) -> RenameResult:
        """Rename `old_name` → `new_name` across all matching files.

        Args:
            old_name: Identifier to replace (whole-word match).
            new_name: Replacement identifier.
            dry_run: If True, compute changes but don't write files.
            extensions: File extensions to search (default: [".py"]).
        """
        exts = set(extensions or [".py"])
        pattern = re.compile(r"\b" + re.escape(old_name) + r"\b")
        files_changed = 0
        total_occurrences = 0
        preview: list[str] = []
        errors: list[str] = []

        all_files = [p for p in self._iter_py_files() if p.suffix in exts]

        for path in all_files:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                errors.append(f"{path}: {e}")
                continue

            count = len(pattern.findall(content))
            if count == 0:
                continue

            new_content = pattern.sub(new_name, content)
            total_occurrences += count
            files_changed += 1
            preview.append(f"  {path} ({count} occurrence{'s' if count > 1 else ''})")

            if not dry_run:
                try:
                    path.write_text(new_content, encoding="utf-8")
                except OSError as e:
                    errors.append(f"{path}: write failed: {e}")

        return RenameResult(
            old_name=old_name,
            new_name=new_name,
            files_changed=files_changed,
            occurrences=total_occurrences,
            preview=preview,
            errors=errors,
        )
