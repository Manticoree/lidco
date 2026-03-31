"""Branch Diff Engine — compare two conversation branches (Q165/Task 938)."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field

from lidco.session.branch_manager import Branch


@dataclass
class BranchDiff:
    """Result of comparing two branches."""

    branch_a: str
    branch_b: str
    conversation_diff: list[str]
    file_diffs: dict[str, str]
    divergence_point: int


class BranchDiffEngine:
    """Compute diffs between two conversation branches."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def diff(self, branch_a: Branch, branch_b: Branch) -> BranchDiff:
        """Return a :class:`BranchDiff` comparing *branch_a* and *branch_b*."""
        divergence = self.find_divergence(branch_a.conversation, branch_b.conversation)
        conv_diff = self._diff_conversations(branch_a.conversation, branch_b.conversation)
        file_diffs = self.diff_files(branch_a.file_snapshots, branch_b.file_snapshots)
        return BranchDiff(
            branch_a=branch_a.branch_id,
            branch_b=branch_b.branch_id,
            conversation_diff=conv_diff,
            file_diffs=file_diffs,
            divergence_point=divergence,
        )

    def find_divergence(self, conv_a: list, conv_b: list) -> int:
        """Return the index where two conversation lists first differ."""
        min_len = min(len(conv_a), len(conv_b))
        for i in range(min_len):
            if conv_a[i] != conv_b[i]:
                return i
        # Identical up to the shorter list — diverge at the shorter length
        if len(conv_a) != len(conv_b):
            return min_len
        return min_len  # fully identical

    def diff_files(self, files_a: dict[str, str], files_b: dict[str, str]) -> dict[str, str]:
        """Return unified diffs for files that differ between the two snapshots."""
        all_keys = sorted(set(files_a) | set(files_b))
        diffs: dict[str, str] = {}
        for key in all_keys:
            content_a = files_a.get(key, "")
            content_b = files_b.get(key, "")
            if content_a == content_b:
                continue
            unified = difflib.unified_diff(
                content_a.splitlines(keepends=True),
                content_b.splitlines(keepends=True),
                fromfile=f"a/{key}",
                tofile=f"b/{key}",
            )
            diffs[key] = "".join(unified)
        return diffs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _diff_conversations(self, conv_a: list[dict], conv_b: list[dict]) -> list[str]:
        """Produce a human-readable diff of two conversation lists."""
        lines_a = [self._msg_line(m) for m in conv_a]
        lines_b = [self._msg_line(m) for m in conv_b]
        return list(difflib.unified_diff(lines_a, lines_b, fromfile="branch_a", tofile="branch_b", lineterm=""))

    @staticmethod
    def _msg_line(msg: dict) -> str:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        preview = content[:80] if isinstance(content, str) else str(content)[:80]
        return f"[{role}] {preview}"
