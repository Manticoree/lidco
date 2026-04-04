"""Post-merge verifier — verify merge results and check regressions (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VerifyResult:
    """Result of a post-merge verification."""

    passed: bool
    missing_files: list[str] = field(default_factory=list)
    extra_files: list[str] = field(default_factory=list)
    content_mismatches: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return (
            len(self.missing_files)
            + len(self.extra_files)
            + len(self.content_mismatches)
        )


@dataclass
class TestResult:
    """A single test result."""

    name: str
    passed: bool
    duration_ms: float = 0.0
    error: str = ""


class PostMergeVerifier:
    """Verify the integrity of a merge result."""

    def verify(
        self,
        before_files: dict[str, str],
        after_files: dict[str, str],
    ) -> VerifyResult:
        """Verify that merged files look correct.

        Checks:
        - No files were accidentally deleted (present in before, missing in after)
        - Detects unexpected new files
        - Detects content that still contains conflict markers
        """
        before_set = set(before_files)
        after_set = set(after_files)

        missing = sorted(before_set - after_set)
        extra = sorted(after_set - before_set)

        content_issues: list[str] = []
        warnings: list[str] = []

        for fpath, content in after_files.items():
            if self._has_conflict_markers(content):
                content_issues.append(fpath)
            if fpath in before_files and before_files[fpath] == content:
                # File unchanged — might be fine, or might indicate merge didn't apply
                pass

        passed = len(missing) == 0 and len(content_issues) == 0

        if extra:
            warnings.append(
                f"{len(extra)} new file(s) appeared after merge."
            )

        return VerifyResult(
            passed=passed,
            missing_files=missing,
            extra_files=extra,
            content_mismatches=content_issues,
            warnings=warnings,
        )

    def check_regressions(self, test_results: list[TestResult]) -> list[str]:
        """Check for regressions in test results.

        Returns list of test names that failed.
        """
        return [t.name for t in test_results if not t.passed]

    def compare_behavior(
        self,
        before_results: list[TestResult],
        after_results: list[TestResult],
    ) -> dict[str, object]:
        """Compare test behavior before and after merge.

        Returns dict with regression/improvement/unchanged counts and details.
        """
        before_map = {t.name: t for t in before_results}
        after_map = {t.name: t for t in after_results}

        regressions: list[str] = []
        improvements: list[str] = []
        unchanged: list[str] = []
        new_tests: list[str] = []
        removed_tests: list[str] = []

        all_names = sorted(set(before_map) | set(after_map))
        for name in all_names:
            b = before_map.get(name)
            a = after_map.get(name)

            if b is None and a is not None:
                new_tests.append(name)
            elif a is None and b is not None:
                removed_tests.append(name)
            elif b is not None and a is not None:
                if b.passed and not a.passed:
                    regressions.append(name)
                elif not b.passed and a.passed:
                    improvements.append(name)
                else:
                    unchanged.append(name)

        return {
            "regressions": regressions,
            "improvements": improvements,
            "unchanged": unchanged,
            "new_tests": new_tests,
            "removed_tests": removed_tests,
            "regression_count": len(regressions),
            "improvement_count": len(improvements),
        }

    def report(
        self,
        verify_result: VerifyResult,
        regressions: list[str] | None = None,
    ) -> str:
        """Generate a human-readable verification report."""
        lines: list[str] = []
        status = "PASS" if verify_result.passed else "FAIL"
        lines.append(f"Post-Merge Verification: {status}")
        lines.append(f"Total issues: {verify_result.total_issues}")

        if verify_result.missing_files:
            lines.append(f"Missing files: {', '.join(verify_result.missing_files)}")
        if verify_result.extra_files:
            lines.append(f"New files: {', '.join(verify_result.extra_files)}")
        if verify_result.content_mismatches:
            lines.append(
                f"Conflict markers found in: "
                f"{', '.join(verify_result.content_mismatches)}"
            )
        for w in verify_result.warnings:
            lines.append(f"Warning: {w}")

        if regressions:
            lines.append(f"Regressions ({len(regressions)}): {', '.join(regressions)}")
        elif regressions is not None:
            lines.append("No regressions detected.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _has_conflict_markers(content: str) -> bool:
        """Check if content contains git conflict markers."""
        markers = ("<<<<<<< ", "=======", ">>>>>>> ")
        for marker in markers:
            if marker in content:
                return True
        return False
