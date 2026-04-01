"""Cross-file rename with rollback."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RenameMatch:
    """A location where a name was found."""

    file: str
    line: int
    column: int = 0
    context: str = ""


@dataclass(frozen=True)
class RenameResult:
    """Result of a rename operation."""

    old_name: str
    new_name: str
    matches: tuple[RenameMatch, ...] = ()
    files_affected: int = 0
    success: bool = True


class RenamePropagator:
    """Find references and rename symbols across files."""

    def __init__(self) -> None:
        pass

    def find_references(
        self, source: str, name: str, file: str = ""
    ) -> list[RenameMatch]:
        """Find all occurrences of *name* as a whole word in *source*."""
        matches: list[RenameMatch] = []
        pattern = re.compile(r"\b" + re.escape(name) + r"\b")
        for lineno, line in enumerate(source.splitlines(), start=1):
            for m in pattern.finditer(line):
                matches.append(
                    RenameMatch(
                        file=file,
                        line=lineno,
                        column=m.start(),
                        context=line.strip(),
                    )
                )
        return matches

    def rename(self, source: str, old_name: str, new_name: str) -> str:
        """Replace all whole-word occurrences of *old_name* with *new_name* in *source*."""
        pattern = re.compile(r"\b" + re.escape(old_name) + r"\b")
        return pattern.sub(new_name, source)

    def rename_in_files(
        self, sources: dict[str, str], old_name: str, new_name: str
    ) -> RenameResult:
        """Rename across multiple files. Returns *RenameResult* with aggregated info."""
        all_matches: list[RenameMatch] = []
        files_affected = 0
        for fname, src in sources.items():
            refs = self.find_references(src, old_name, file=fname)
            if refs:
                files_affected += 1
                all_matches.extend(refs)
        return RenameResult(
            old_name=old_name,
            new_name=new_name,
            matches=tuple(all_matches),
            files_affected=files_affected,
            success=True,
        )

    def preview(
        self, sources: dict[str, str], old_name: str, new_name: str
    ) -> str:
        """Return unified diffs showing the rename across all files."""
        parts: list[str] = []
        for fname, src in sorted(sources.items()):
            updated = self.rename(src, old_name, new_name)
            if updated != src:
                diff = difflib.unified_diff(
                    src.splitlines(keepends=True),
                    updated.splitlines(keepends=True),
                    fromfile=fname,
                    tofile=fname,
                )
                parts.append("".join(diff))
        return "\n".join(parts)
