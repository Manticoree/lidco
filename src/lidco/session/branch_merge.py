"""Branch Merge — merge two conversation branches (Q165/Task 939)."""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.session.branch_manager import Branch
from lidco.session.branch_diff import BranchDiffEngine


@dataclass
class MergeResult:
    """Outcome of merging two branches."""

    success: bool
    merged_conversation: list[dict]
    merged_files: dict[str, str]
    conflicts: list[str]


class BranchMerger:
    """Merge a *source* branch into a *target* branch."""

    def __init__(self) -> None:
        self._diff_engine = BranchDiffEngine()

    def merge(self, source: Branch, target: Branch) -> MergeResult:
        """Merge *source* into *target*.

        Conversation: append source messages after the divergence point.
        Files: source wins for files only changed in source; conflict if
        both branches changed the same file differently from the common
        ancestor content (approximated by matching at divergence).
        """
        divergence = self._diff_engine.find_divergence(
            source.conversation, target.conversation
        )

        # Build merged conversation: target up to end + source after divergence
        merged_conv = list(target.conversation)
        source_extra = source.conversation[divergence:]
        merged_conv.extend(source_extra)

        # Merge files
        merged_files = dict(target.file_snapshots)
        conflicts: list[str] = []

        all_keys = sorted(set(source.file_snapshots) | set(target.file_snapshots))
        for key in all_keys:
            src_content = source.file_snapshots.get(key)
            tgt_content = target.file_snapshots.get(key)

            if src_content == tgt_content:
                # Unchanged or identical in both — keep target (already there)
                if src_content is not None:
                    merged_files[key] = src_content
                continue

            if src_content is not None and tgt_content is None:
                # Only in source — add it
                merged_files[key] = src_content
                continue

            if src_content is None and tgt_content is not None:
                # Only in target — already there
                continue

            # Both have the file but content differs — conflict
            assert src_content is not None and tgt_content is not None
            conflicts.append(key)
            # Source wins for the merged output, but we flag the conflict
            merged_files[key] = src_content

        return MergeResult(
            success=len(conflicts) == 0,
            merged_conversation=merged_conv,
            merged_files=merged_files,
            conflicts=conflicts,
        )
