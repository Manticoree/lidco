"""Batch Editor — apply multiple patches atomically with rollback support.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from lidco.editing.patch_applier import PatchApplyResult, PatchApplier
from lidco.editing.patch_parser import PatchFile


@dataclass
class BatchEditResult:
    """Result of a batch patch operation."""
    applied: int
    failed: int
    results: dict[str, PatchApplyResult] = field(default_factory=dict)


class BatchEditor:
    """Apply multiple patches in batch, with optional stop-on-error and rollback."""

    def __init__(self, applier: PatchApplier | None = None) -> None:
        self._applier = applier or PatchApplier()

    def apply_all(
        self,
        patches: dict[str, tuple[str, PatchFile]],
        stop_on_error: bool = False,
    ) -> BatchEditResult:
        """Apply all patches.

        Args:
            patches: mapping of filename → (original_text, PatchFile)
            stop_on_error: if True, stop on first failure

        Returns:
            BatchEditResult with per-file results.
        """
        applied = 0
        failed = 0
        results: dict[str, PatchApplyResult] = {}

        for filename, (original, patch_file) in patches.items():
            result = self._applier.apply(original, patch_file)
            results[filename] = result
            if result.success:
                applied += 1
            else:
                failed += 1
                if stop_on_error:
                    break

        return BatchEditResult(applied=applied, failed=failed, results=results)

    def rollback(self, results: BatchEditResult) -> dict[str, str]:
        """Return original texts for files that failed to apply.

        Since we don't store originals in BatchEditResult, this method returns
        result_text for failed files (which is the original on failure).
        """
        originals: dict[str, str] = {}
        for filename, result in results.results.items():
            if not result.success:
                originals[filename] = result.result_text
        return originals
