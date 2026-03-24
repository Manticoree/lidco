"""MigrationAgent — automated codebase-wide regex refactor."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MigrationRule:
    name: str
    description: str
    find_pattern: str  # regex
    replace_template: str
    file_glob: str = "**/*.py"


@dataclass
class MigrationPlan:
    rule: MigrationRule
    affected_files: list[str]
    change_count: int
    preview: dict[str, str]  # file -> new content


@dataclass
class MigrationResult:
    applied_files: list[str]
    skipped: list[str]
    test_result: str
    success: bool


class MigrationAgent:
    """Plan and execute a regex-based codebase-wide migration."""

    def __init__(
        self,
        project_dir: Path | None = None,
        test_cmd: str = "python -m pytest -q --tb=no",
    ) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._test_cmd = test_cmd

    def plan(self, rule: MigrationRule) -> MigrationPlan:
        """Scan files and produce a migration plan with previews."""
        pattern = re.compile(rule.find_pattern)
        affected: list[str] = []
        preview: dict[str, str] = {}
        change_count = 0

        # rglob already adds recursion, so strip leading "**/" if present
        glob_pattern = rule.file_glob
        if glob_pattern.startswith("**/"):
            glob_pattern = glob_pattern[3:]
        for path in self._project_dir.rglob(glob_pattern):
            if not path.is_file():
                continue
            try:
                original = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            new_content, count = pattern.subn(rule.replace_template, original)
            if count > 0:
                rel = str(path.relative_to(self._project_dir))
                affected.append(rel)
                preview[rel] = new_content
                change_count += count

        return MigrationPlan(
            rule=rule,
            affected_files=affected,
            change_count=change_count,
            preview=preview,
        )

    def execute(self, plan: MigrationPlan) -> MigrationResult:
        """Apply all planned changes, run tests, return result."""
        applied: list[str] = []
        skipped: list[str] = []

        for rel_path, new_content in plan.preview.items():
            abs_path = self._project_dir / rel_path
            try:
                abs_path.write_text(new_content, encoding="utf-8")
                applied.append(rel_path)
            except OSError:
                skipped.append(rel_path)

        test_result = self._run_tests()
        success = "failed" not in test_result.lower() and "error" not in test_result.lower()

        return MigrationResult(
            applied_files=applied,
            skipped=skipped,
            test_result=test_result,
            success=success,
        )

    def _run_tests(self) -> str:
        try:
            result = subprocess.run(
                self._test_cmd,
                shell=True,
                cwd=self._project_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.stdout[-500:] if result.stdout else result.stderr[-500:] or "ok"
        except Exception as exc:
            return str(exc)
