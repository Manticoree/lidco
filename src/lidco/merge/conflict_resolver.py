"""Conflict resolver — strategies to resolve three-way merge conflicts (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.merge.three_way import MergeConflict, MergeResult


@dataclass
class Resolution:
    """A resolution for a single merge conflict."""

    conflict_index: int
    strategy: str  # "ours" | "theirs" | "both" | "custom"
    resolved_text: str


class ConflictResolver:
    """Resolve merge conflicts using various strategies."""

    def resolve_ours(self, conflict: MergeConflict) -> Resolution:
        """Resolve by keeping our version."""
        return Resolution(
            conflict_index=0,
            strategy="ours",
            resolved_text=conflict.ours_text,
        )

    def resolve_theirs(self, conflict: MergeConflict) -> Resolution:
        """Resolve by keeping their version."""
        return Resolution(
            conflict_index=0,
            strategy="theirs",
            resolved_text=conflict.theirs_text,
        )

    def resolve_both(self, conflict: MergeConflict) -> Resolution:
        """Resolve by concatenating ours then theirs."""
        combined = conflict.ours_text + conflict.theirs_text
        return Resolution(
            conflict_index=0,
            strategy="both",
            resolved_text=combined,
        )

    def resolve_custom(self, conflict: MergeConflict, text: str) -> Resolution:
        """Resolve with custom text."""
        return Resolution(
            conflict_index=0,
            strategy="custom",
            resolved_text=text,
        )

    def apply_resolutions(
        self, merge_result: MergeResult, resolutions: list[Resolution]
    ) -> str:
        """Apply resolutions to a merge result to produce final text.

        Replaces conflict markers in the merged text with resolved text.
        """
        if not merge_result.has_conflicts:
            return merge_result.merged

        # Build a resolution lookup by conflict index
        res_map: dict[int, Resolution] = {}
        for r in resolutions:
            res_map[r.conflict_index] = r

        lines = merge_result.merged.splitlines(keepends=True)
        output: list[str] = []
        conflict_idx = 0
        in_conflict = False
        in_theirs = False

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.rstrip("\n")

            if stripped == "<<<<<<< ours":
                in_conflict = True
                in_theirs = False
                if conflict_idx in res_map:
                    # Insert resolved text
                    resolved = res_map[conflict_idx].resolved_text
                    if resolved and not resolved.endswith("\n"):
                        resolved += "\n"
                    output.append(resolved)
                # Skip until >>>>>>> theirs
                while i < len(lines):
                    if lines[i].rstrip("\n") == ">>>>>>> theirs":
                        break
                    i += 1
                conflict_idx += 1
                in_conflict = False
                i += 1
                continue

            if not in_conflict:
                output.append(line)
            i += 1

        return "".join(output)

    def auto_resolve(self, conflicts: list[MergeConflict]) -> list[Resolution]:
        """Auto-resolve trivial conflicts (whitespace-only differences)."""
        resolutions: list[Resolution] = []
        for idx, conflict in enumerate(conflicts):
            ours_stripped = conflict.ours_text.strip()
            theirs_stripped = conflict.theirs_text.strip()

            if ours_stripped == theirs_stripped:
                # Whitespace-only difference — take ours
                resolutions.append(
                    Resolution(
                        conflict_index=idx,
                        strategy="ours",
                        resolved_text=conflict.ours_text,
                    )
                )
        return resolutions
