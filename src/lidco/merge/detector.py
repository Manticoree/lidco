"""Conflict detector — predict and detect merge conflicts (stdlib only)."""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    """Conflict severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Conflict:
    """A detected merge conflict between two branches."""

    file_path: str
    line_start: int
    line_end: int
    text_a: str
    text_b: str
    base_text: str = ""
    severity: str = "medium"


@dataclass
class SimulationResult:
    """Result of a merge simulation."""

    conflicts: list[Conflict] = field(default_factory=list)
    clean_files: list[str] = field(default_factory=list)
    conflicting_files: list[str] = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def total_conflicts(self) -> int:
        return len(self.conflicts)


class ConflictDetector:
    """Detect and predict merge conflicts between branches."""

    def detect(
        self,
        base: dict[str, str],
        branch_a: dict[str, str],
        branch_b: dict[str, str],
    ) -> list[Conflict]:
        """Detect conflicts between two branches relative to a common base.

        Args:
            base: mapping of file_path -> file_content for the base revision
            branch_a: mapping of file_path -> file_content for branch A
            branch_b: mapping of file_path -> file_content for branch B

        Returns:
            list of Conflict objects for overlapping changes.
        """
        conflicts: list[Conflict] = []
        all_files = set(base) | set(branch_a) | set(branch_b)

        for fpath in sorted(all_files):
            base_text = base.get(fpath, "")
            a_text = branch_a.get(fpath, "")
            b_text = branch_b.get(fpath, "")

            # If only one branch changed the file, no conflict
            a_changed = a_text != base_text
            b_changed = b_text != base_text
            if not (a_changed and b_changed):
                continue

            # Both changed — find overlapping regions
            file_conflicts = self._find_overlapping_changes(
                fpath, base_text, a_text, b_text
            )
            conflicts.extend(file_conflicts)

        return conflicts

    def predict_affected(
        self, files_a: list[str], files_b: list[str]
    ) -> list[str]:
        """Predict which files may conflict based on changed file lists.

        Returns files modified by both branches.
        """
        set_a = set(files_a)
        set_b = set(files_b)
        return sorted(set_a & set_b)

    def severity_score(self, conflict: Conflict) -> float:
        """Compute a severity score for a conflict (0.0–1.0)."""
        span = conflict.line_end - conflict.line_start + 1
        a_len = len(conflict.text_a)
        b_len = len(conflict.text_b)

        # Larger spans and bigger divergence score higher
        span_factor = min(span / 50.0, 1.0)
        size_factor = min((a_len + b_len) / 2000.0, 1.0)

        # Check similarity — lower similarity means higher severity
        ratio = difflib.SequenceMatcher(None, conflict.text_a, conflict.text_b).ratio()
        divergence_factor = 1.0 - ratio

        score = 0.3 * span_factor + 0.3 * size_factor + 0.4 * divergence_factor
        return round(min(max(score, 0.0), 1.0), 4)

    def simulate_merge(
        self,
        files_a: dict[str, str],
        files_b: dict[str, str],
        base: dict[str, str] | None = None,
    ) -> SimulationResult:
        """Simulate a merge and report expected conflicts.

        Args:
            files_a: file contents for branch A
            files_b: file contents for branch B
            base: optional common base (defaults to empty for each file)
        """
        if base is None:
            base = {}

        conflicts = self.detect(base, files_a, files_b)
        conflicting = sorted({c.file_path for c in conflicts})

        all_files = sorted(set(files_a) | set(files_b))
        clean = [f for f in all_files if f not in conflicting]

        return SimulationResult(
            conflicts=conflicts,
            clean_files=clean,
            conflicting_files=conflicting,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_overlapping_changes(
        self,
        file_path: str,
        base_text: str,
        a_text: str,
        b_text: str,
    ) -> list[Conflict]:
        """Find overlapping changed regions in a single file."""
        base_lines = base_text.splitlines(keepends=True)
        a_lines = a_text.splitlines(keepends=True)
        b_lines = b_text.splitlines(keepends=True)

        a_changed = self._changed_ranges(base_lines, a_lines)
        b_changed = self._changed_ranges(base_lines, b_lines)

        conflicts: list[Conflict] = []
        for a_start, a_end in a_changed:
            for b_start, b_end in b_changed:
                # Overlap check
                if a_start <= b_end and b_start <= a_end:
                    overlap_start = max(a_start, b_start)
                    overlap_end = min(a_end, b_end)
                    conflicts.append(
                        Conflict(
                            file_path=file_path,
                            line_start=overlap_start,
                            line_end=overlap_end,
                            text_a="".join(
                                a_lines[a_start : a_end + 1]
                                if a_start < len(a_lines)
                                else []
                            ),
                            text_b="".join(
                                b_lines[b_start : b_end + 1]
                                if b_start < len(b_lines)
                                else []
                            ),
                            base_text="".join(
                                base_lines[overlap_start : overlap_end + 1]
                                if overlap_start < len(base_lines)
                                else []
                            ),
                        )
                    )

        return conflicts

    @staticmethod
    def _changed_ranges(
        base_lines: list[str], branch_lines: list[str]
    ) -> list[tuple[int, int]]:
        """Return list of (start, end) line ranges changed relative to base."""
        matcher = difflib.SequenceMatcher(None, base_lines, branch_lines)
        ranges: list[tuple[int, int]] = []
        for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
            if tag != "equal":
                start = i1
                end = max(i2 - 1, i1)
                ranges.append((start, end))
        return ranges
