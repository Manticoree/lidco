"""PRDescriptionGenerator — generate PR descriptions from commits and diffs (stdlib only)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PRDescription:
    """Immutable PR description output."""
    summary: str
    changes: list[str]
    test_plan: str
    body: str


class PRDescriptionGenerator:
    """Generate structured PR descriptions from commit messages and diffs.

    Parameters
    ----------
    max_summary_length:
        Maximum character length for the summary line.
    """

    def __init__(self, max_summary_length: int = 200) -> None:
        self._max_summary_length = max_summary_length
        self._templates: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, commits: list[str], diff: str) -> str:
        """Generate a full PR description body from commits and diff."""
        summ = self.summary(diff)
        changes = self.changes_list(diff)
        plan = self.test_plan(diff)
        data = {"summary": summ, "changes": changes, "test_plan": plan}
        return self.template(data)

    def summary(self, diff: str) -> str:
        """Produce a one-line summary from the diff."""
        files = self._extract_files(diff)
        if not files:
            return "No changes detected."
        n = len(files)
        if n == 1:
            text = f"Update {files[0]}"
        elif n <= 3:
            text = f"Update {', '.join(files)}"
        else:
            text = f"Update {n} files including {files[0]}"
        return text[: self._max_summary_length]

    def changes_list(self, diff: str) -> list[str]:
        """Return a list of human-readable change descriptions from a unified diff."""
        results: list[str] = []
        files = self._extract_files(diff)
        additions = self._count_additions(diff)
        deletions = self._count_deletions(diff)
        for f in files:
            results.append(f"Modified {f}")
        if additions:
            results.append(f"{additions} line(s) added")
        if deletions:
            results.append(f"{deletions} line(s) deleted")
        return results

    def test_plan(self, diff: str) -> str:
        """Generate a test plan based on the diff contents."""
        files = self._extract_files(diff)
        test_files = [f for f in files if "test" in f.lower()]
        src_files = [f for f in files if "test" not in f.lower()]
        lines: list[str] = []
        if test_files:
            lines.append(f"- Run modified test files: {', '.join(test_files)}")
        if src_files:
            lines.append(f"- Verify changes in: {', '.join(src_files)}")
        if not lines:
            lines.append("- No specific test plan (no files changed)")
        return "\n".join(lines)

    def template(self, data: dict[str, object]) -> str:
        """Format a PR description from a data dict containing summary, changes, test_plan."""
        summary = data.get("summary", "")
        changes = data.get("changes", [])
        test_plan = data.get("test_plan", "")
        changes_block = "\n".join(f"- {c}" for c in changes) if changes else "- No changes"
        return (
            f"## Summary\n{summary}\n\n"
            f"## Changes\n{changes_block}\n\n"
            f"## Test Plan\n{test_plan}"
        )

    def add_template(self, name: str, tmpl: str) -> None:
        """Register a named template string."""
        self._templates = {**self._templates, name: tmpl}

    def get_template(self, name: str) -> str | None:
        """Return a named template or None."""
        return self._templates.get(name)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_files(diff: str) -> list[str]:
        """Extract file paths from unified diff headers."""
        pattern = re.compile(r"^(?:---|\+\+\+) [ab]/(.+)$", re.MULTILINE)
        files: list[str] = []
        seen: set[str] = set()
        for m in pattern.finditer(diff):
            path = m.group(1)
            if path not in seen:
                seen.add(path)
                files.append(path)
        return files

    @staticmethod
    def _count_additions(diff: str) -> int:
        return sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))

    @staticmethod
    def _count_deletions(diff: str) -> int:
        return sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
