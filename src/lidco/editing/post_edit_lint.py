"""PostEditLintHook — run formatters and linters after file edits (Task 701)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LintHookResult:
    files_processed: int
    auto_fixed: int
    needs_manual: int
    errors: list[str]
    blocked: bool


class PostEditLintHook:
    """Run formatters and linters automatically after file edits."""

    def __init__(
        self,
        formatter_registry=None,
        lint_fix_loop=None,
        severity_threshold: str = "error",
    ):
        self._formatter_registry = formatter_registry
        self._lint_fix_loop = lint_fix_loop
        self._severity_threshold = severity_threshold
        self._enabled: bool = True

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def on_apply(self, changed_files: list[str], dry_run: bool = False) -> LintHookResult:
        """Run formatters and linters on changed files."""
        if not self._enabled:
            return LintHookResult(
                files_processed=0,
                auto_fixed=0,
                needs_manual=0,
                errors=[],
                blocked=False,
            )

        files_processed = 0
        auto_fixed = 0
        needs_manual = 0
        errors: list[str] = []

        for filepath in changed_files:
            files_processed += 1

            # Run formatter if available
            if self._formatter_registry is not None:
                try:
                    result = self._formatter_registry.format_file(filepath, check_only=dry_run)
                    if result.changed:
                        auto_fixed += 1
                    if not result.success:
                        errors.append(f"Formatter error on {filepath}: {result.error}")
                        needs_manual += 1
                except Exception as exc:
                    errors.append(f"Formatter failed on {filepath}: {exc}")

            # Run lint fix loop if available
            if self._lint_fix_loop is not None:
                try:
                    lint_results = self._lint_fix_loop.run_lint([filepath])
                    for lr in lint_results:
                        if not lr.clean:
                            needs_manual += 1
                            for issue in lr.errors:
                                errors.append(f"Lint: {filepath}:{issue.line}: {issue.message}")
                except Exception as exc:
                    errors.append(f"Lint failed on {filepath}: {exc}")

        blocked = bool(errors) and self._severity_threshold == "error"

        return LintHookResult(
            files_processed=files_processed,
            auto_fixed=auto_fixed,
            needs_manual=needs_manual,
            errors=errors,
            blocked=blocked,
        )

    def register_with_smart_apply(self, smart_apply) -> None:
        """Register on_apply as after-apply callback on SmartApply instance."""
        if hasattr(smart_apply, "after_apply_callback"):
            smart_apply.after_apply_callback = self.on_apply
        elif hasattr(smart_apply, "register_callback"):
            smart_apply.register_callback("after_apply", self.on_apply)
