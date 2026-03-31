"""Three-way merge — line-by-line merge with conflict detection (stdlib only)."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field


@dataclass
class MergeConflict:
    """A single conflict region from a three-way merge."""

    start_line: int
    base_text: str
    ours_text: str
    theirs_text: str


@dataclass
class MergeResult:
    """Result of a three-way merge."""

    merged: str
    conflicts: list[MergeConflict] = field(default_factory=list)
    has_conflicts: bool = False
    auto_resolved: int = 0


class ThreeWayMerge:
    """Line-by-line three-way merge engine."""

    def merge(self, base: str, ours: str, theirs: str) -> MergeResult:
        """Perform a three-way merge of *base*, *ours*, and *theirs*.

        Returns a ``MergeResult`` with the merged text and any conflicts.
        """
        base_lines = base.splitlines(keepends=True)
        ours_lines = ours.splitlines(keepends=True)
        theirs_lines = theirs.splitlines(keepends=True)

        # Get opcodes for ours-vs-base and theirs-vs-base
        sm_ours = difflib.SequenceMatcher(None, base_lines, ours_lines)
        sm_theirs = difflib.SequenceMatcher(None, base_lines, theirs_lines)

        ours_changes = _build_change_map(sm_ours.get_opcodes(), base_lines, ours_lines)
        theirs_changes = _build_change_map(sm_theirs.get_opcodes(), base_lines, theirs_lines)

        merged_lines: list[str] = []
        conflicts: list[MergeConflict] = []
        auto_resolved = 0

        all_base_indices = set(ours_changes.keys()) | set(theirs_changes.keys())

        i = 0
        while i < len(base_lines) or i in all_base_indices:
            ours_entry = ours_changes.get(i)
            theirs_entry = theirs_changes.get(i)

            if ours_entry is None and theirs_entry is None:
                # No change from either side — keep base
                if i < len(base_lines):
                    merged_lines.append(base_lines[i])
                i += 1
                continue

            # Both sides changed the same region
            if ours_entry is not None and theirs_entry is not None:
                o_base, o_new, o_end = ours_entry
                t_base, t_new, t_end = theirs_entry

                if o_new == t_new:
                    # Both made the same change — auto-resolve
                    merged_lines.extend(o_new)
                    auto_resolved += 1
                    i = max(o_end, t_end)
                    continue

                # Real conflict
                conflict = MergeConflict(
                    start_line=i,
                    base_text="".join(o_base),
                    ours_text="".join(o_new),
                    theirs_text="".join(t_new),
                )
                conflicts.append(conflict)
                # Put conflict markers in merged output
                merged_lines.append("<<<<<<< ours\n")
                merged_lines.extend(o_new)
                merged_lines.append("=======\n")
                merged_lines.extend(t_new)
                merged_lines.append(">>>>>>> theirs\n")
                i = max(o_end, t_end)
                continue

            # Only one side changed
            if ours_entry is not None:
                o_base, o_new, o_end = ours_entry
                merged_lines.extend(o_new)
                auto_resolved += 1
                i = o_end
                continue

            if theirs_entry is not None:
                t_base, t_new, t_end = theirs_entry
                merged_lines.extend(t_new)
                auto_resolved += 1
                i = t_end
                continue

            i += 1

        merged_text = "".join(merged_lines)
        return MergeResult(
            merged=merged_text,
            conflicts=conflicts,
            has_conflicts=len(conflicts) > 0,
            auto_resolved=auto_resolved,
        )

    def can_auto_merge(self, base: str, ours: str, theirs: str) -> bool:
        """Return True if base/ours/theirs can merge without conflicts."""
        result = self.merge(base, ours, theirs)
        return not result.has_conflicts

    def format_conflicts(self, result: MergeResult) -> str:
        """Format conflicts in git-style ``<<<<<<< ours`` markers."""
        if not result.conflicts:
            return ""
        parts: list[str] = []
        for idx, c in enumerate(result.conflicts):
            parts.append(f"Conflict {idx + 1} (line {c.start_line}):")
            parts.append("<<<<<<< ours")
            parts.append(c.ours_text.rstrip("\n"))
            parts.append("=======")
            parts.append(c.theirs_text.rstrip("\n"))
            parts.append(">>>>>>> theirs")
            parts.append("")
        return "\n".join(parts)


def _build_change_map(
    opcodes: list[tuple[str, int, int, int, int]],
    base_lines: list[str],
    new_lines: list[str],
) -> dict[int, tuple[list[str], list[str], int]]:
    """Build a map from base-line-index to (base_segment, new_segment, end_index).

    Only non-equal opcodes are included.
    """
    changes: dict[int, tuple[list[str], list[str], int]] = {}
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue
        base_seg = base_lines[i1:i2]
        new_seg = new_lines[j1:j2]
        changes[i1] = (base_seg, new_seg, i2)
    return changes
