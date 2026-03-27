"""Git Conflict Resolver — parse and resolve git merge conflicts (stdlib only).

Parses conflict markers (<<<<<<< / ======= / >>>>>>>) from file content,
categorises conflicts by type, and suggests/applies resolutions.
Like VS Code's merge conflict editor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConflictError(Exception):
    """Raised when conflict parsing or resolution fails."""


class ConflictType(str, Enum):
    IDENTICAL = "identical"          # both sides same → auto-resolve
    OURS_ONLY = "ours_only"          # theirs is empty → take ours
    THEIRS_ONLY = "theirs_only"      # ours is empty → take theirs
    BOTH_EMPTY = "both_empty"        # both empty → take either
    ADDITION = "addition"            # one side adds lines the other doesn't have
    COMPLEX = "complex"              # requires manual resolution


class Resolution(str, Enum):
    OURS = "ours"
    THEIRS = "theirs"
    BOTH = "both"           # keep both (ours first, then theirs)
    BOTH_REVERSED = "both_reversed"
    MANUAL = "manual"       # cannot auto-resolve


@dataclass
class Conflict:
    """A single conflict block parsed from a file."""

    index: int                    # 0-based position in file
    ours_label: str               # branch name from <<<<<<< line
    theirs_label: str             # branch name from >>>>>>> line
    ours_lines: list[str]         # lines in our version
    theirs_lines: list[str]       # lines in their version
    base_lines: list[str] = field(default_factory=list)  # |||||||| diff3 base
    start_line: int = 0           # 1-based line in original file
    end_line: int = 0

    @property
    def conflict_type(self) -> ConflictType:
        ours = [ln.strip() for ln in self.ours_lines]
        theirs = [ln.strip() for ln in self.theirs_lines]
        if ours == theirs:
            return ConflictType.IDENTICAL
        if not any(ln for ln in ours):
            return ConflictType.OURS_ONLY if not any(ln for ln in theirs) else ConflictType.THEIRS_ONLY
        if not any(ln for ln in theirs):
            return ConflictType.OURS_ONLY
        if not any(ln for ln in ours) and not any(ln for ln in theirs):
            return ConflictType.BOTH_EMPTY
        return ConflictType.COMPLEX

    def suggested_resolution(self) -> Resolution:
        ct = self.conflict_type
        if ct == ConflictType.IDENTICAL:
            return Resolution.OURS
        if ct == ConflictType.OURS_ONLY:
            return Resolution.OURS
        if ct == ConflictType.THEIRS_ONLY:
            return Resolution.THEIRS
        if ct == ConflictType.BOTH_EMPTY:
            return Resolution.OURS
        return Resolution.MANUAL

    def resolve(self, resolution: Resolution) -> list[str]:
        """Apply a resolution and return the resolved lines."""
        if resolution == Resolution.OURS:
            return list(self.ours_lines)
        if resolution == Resolution.THEIRS:
            return list(self.theirs_lines)
        if resolution == Resolution.BOTH:
            return list(self.ours_lines) + list(self.theirs_lines)
        if resolution == Resolution.BOTH_REVERSED:
            return list(self.theirs_lines) + list(self.ours_lines)
        raise ConflictError(f"Cannot auto-resolve: {resolution}")

    def summary(self) -> str:
        return (
            f"Conflict #{self.index + 1} (line {self.start_line}): "
            f"{self.conflict_type.value} — suggested: {self.suggested_resolution().value}"
        )


@dataclass
class ResolveResult:
    """Result of resolving conflicts in a file."""

    content: str
    resolved: int
    unresolved: int
    conflicts: list[Conflict] = field(default_factory=list)

    @property
    def all_resolved(self) -> bool:
        return self.unresolved == 0

    def summary(self) -> str:
        total = self.resolved + self.unresolved
        return (
            f"Resolved {self.resolved}/{total} conflicts "
            f"({'clean' if self.all_resolved else f'{self.unresolved} need manual review'})"
        )


class ConflictResolver:
    """Parse, analyse, and resolve git merge conflicts.

    Usage::

        resolver = ConflictResolver()
        conflicts = resolver.parse(file_content)
        for c in conflicts:
            print(c.summary())

        result = resolver.auto_resolve(file_content)
        print(result.summary())
        open("file.py", "w").write(result.content)
    """

    _OURS_RE = re.compile(r"^<<<<<<< (.+)$")
    _SEP_RE = re.compile(r"^=======$")
    _BASE_RE = re.compile(r"^\|\|\|\|\|\|\| (.+)$")
    _THEIRS_RE = re.compile(r"^>>>>>>> (.+)$")

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------ #
    # Parsing                                                              #
    # ------------------------------------------------------------------ #

    def has_conflicts(self, content: str) -> bool:
        return bool(re.search(self._OURS_RE.pattern, content, re.MULTILINE))

    def parse(self, content: str) -> list[Conflict]:
        """Extract all conflict blocks from file content."""
        lines = content.splitlines(keepends=True)
        conflicts: list[Conflict] = []
        i = 0
        conflict_index = 0

        while i < len(lines):
            line = lines[i].rstrip("\n").rstrip("\r")
            m = self._OURS_RE.match(line)
            if m:
                start_line = i + 1  # 1-based
                ours_label = m.group(1)
                ours_lines: list[str] = []
                base_lines: list[str] = []
                theirs_lines: list[str] = []
                theirs_label = ""
                i += 1
                section = "ours"

                while i < len(lines):
                    ln = lines[i].rstrip("\n").rstrip("\r")
                    if self._BASE_RE.match(ln):
                        section = "base"
                        i += 1
                        continue
                    if self._SEP_RE.match(ln):
                        section = "theirs"
                        i += 1
                        continue
                    tm = self._THEIRS_RE.match(ln)
                    if tm:
                        theirs_label = tm.group(1)
                        end_line = i + 1
                        conflicts.append(Conflict(
                            index=conflict_index,
                            ours_label=ours_label,
                            theirs_label=theirs_label,
                            ours_lines=ours_lines,
                            theirs_lines=theirs_lines,
                            base_lines=base_lines,
                            start_line=start_line,
                            end_line=end_line,
                        ))
                        conflict_index += 1
                        i += 1
                        break
                    if section == "ours":
                        ours_lines.append(lines[i].rstrip("\n").rstrip("\r"))
                    elif section == "base":
                        base_lines.append(lines[i].rstrip("\n").rstrip("\r"))
                    else:
                        theirs_lines.append(lines[i].rstrip("\n").rstrip("\r"))
                    i += 1
            else:
                i += 1

        return conflicts

    def count(self, content: str) -> int:
        return len(self.parse(content))

    # ------------------------------------------------------------------ #
    # Resolution                                                           #
    # ------------------------------------------------------------------ #

    def auto_resolve(
        self,
        content: str,
        prefer: Resolution = Resolution.OURS,
    ) -> ResolveResult:
        """Automatically resolve conflicts where possible."""
        conflicts = self.parse(content)
        if not conflicts:
            return ResolveResult(content=content, resolved=0, unresolved=0,
                                 conflicts=conflicts)

        lines = content.splitlines(keepends=True)
        resolved_count = 0
        unresolved_count = 0
        result_lines: list[str] = []
        i = 0

        conflict_map: dict[int, Conflict] = {}  # line index (0-based) → conflict
        for c in conflicts:
            conflict_map[c.start_line - 1] = c

        while i < len(lines):
            if i in conflict_map:
                c = conflict_map[i]
                suggestion = c.suggested_resolution()
                if suggestion == Resolution.MANUAL:
                    suggestion = prefer
                    unresolved_count += 1
                else:
                    resolved_count += 1
                resolved_lines = c.resolve(suggestion)
                for rl in resolved_lines:
                    result_lines.append(rl + "\n")
                # Skip to end of conflict block
                i = c.end_line  # end_line is 1-based → next 0-based index
            else:
                ln = lines[i]
                # Skip conflict marker lines that are part of a conflict block
                stripped = ln.rstrip("\n").rstrip("\r")
                if (self._OURS_RE.match(stripped) or self._SEP_RE.match(stripped) or
                        self._THEIRS_RE.match(stripped) or self._BASE_RE.match(stripped)):
                    i += 1
                    continue
                result_lines.append(ln)
                i += 1

        return ResolveResult(
            content="".join(result_lines),
            resolved=resolved_count,
            unresolved=unresolved_count,
            conflicts=conflicts,
        )

    def resolve_conflict(
        self,
        content: str,
        conflict_index: int,
        resolution: Resolution,
    ) -> str:
        """Resolve a single conflict by index and return updated content."""
        conflicts = self.parse(content)
        if conflict_index >= len(conflicts):
            raise ConflictError(f"Conflict index {conflict_index} out of range")
        c = conflicts[conflict_index]
        resolved_lines = c.resolve(resolution)

        lines = content.splitlines(keepends=True)
        # Replace from start_line-1 to end_line (inclusive) with resolved
        pre = lines[:c.start_line - 1]
        post = lines[c.end_line:]
        new_lines = pre + [ln + "\n" for ln in resolved_lines] + post
        return "".join(new_lines)

    def diff_summary(self, conflicts: list[Conflict]) -> dict[str, Any]:
        types: dict[str, int] = {}
        suggestions: dict[str, int] = {}
        for c in conflicts:
            ct = c.conflict_type.value
            types[ct] = types.get(ct, 0) + 1
            sg = c.suggested_resolution().value
            suggestions[sg] = suggestions.get(sg, 0) + 1
        return {
            "total": len(conflicts),
            "by_type": types,
            "by_suggestion": suggestions,
            "auto_resolvable": sum(
                1 for c in conflicts if c.suggested_resolution() != Resolution.MANUAL
            ),
        }
