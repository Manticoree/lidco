"""
PR Description Generator — GitHub Copilot-style automated PR descriptions.

Uses `git log` and `git diff` to extract facts about a branch, then passes
them to an LLM callback to generate a structured PR description with:
  - Title
  - Summary (bullet points)
  - Detailed changes (per file / per area)
  - Test plan (checklist)
  - Breaking changes flag

The LLM callback is injected (no hard model dependency).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PRDescription:
    title: str
    summary: list[str]          # brief bullet points
    changes: list[str]          # detailed change lines
    test_plan: list[str]        # checklist items
    breaking_changes: list[str] # empty list = no breaking changes

    @property
    def has_breaking_changes(self) -> bool:
        return bool(self.breaking_changes)


@dataclass
class DiffStats:
    base_branch: str
    head_branch: str
    commit_count: int
    files_changed: list[str]
    insertions: int
    deletions: int
    commits: list[dict[str, str]]  # [{hash, author, date, message}]
    diff_summary: str              # short unified diff (truncated)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

_LOG_FMT = "%H%x1f%an%x1f%ai%x1f%s%x1e"


def _run_git(args: list[str], cwd: str) -> str:
    try:
        proc = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=20,
        )
        return proc.stdout
    except Exception:
        return ""


def _parse_log(raw: str) -> list[dict[str, str]]:
    commits = []
    for block in raw.strip().split("\x1e"):
        block = block.strip()
        if not block:
            continue
        parts = block.split("\x1f")
        if len(parts) >= 4:
            commits.append({
                "hash": parts[0].strip(),
                "author": parts[1].strip(),
                "date": parts[2].strip(),
                "message": parts[3].strip(),
            })
    return commits


def _parse_numstat(raw: str) -> tuple[int, int, list[str]]:
    """Parse `git diff --numstat` output → (insertions, deletions, files)."""
    insertions = deletions = 0
    files: list[str] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            try:
                insertions += int(parts[0])
                deletions += int(parts[1])
            except ValueError:
                pass
            files.append(parts[2].strip())
    return insertions, deletions, files


# ---------------------------------------------------------------------------
# PRDescriptionGenerator
# ---------------------------------------------------------------------------

class PRDescriptionGenerator:
    """
    Generate PR descriptions from git metadata + LLM.

    Parameters
    ----------
    project_root : str | None
        Root of the git repository.
    llm_callback : Callable[[str], str] | None
        Accepts a prompt string, returns the LLM response.
        When None, a rule-based fallback description is generated.
    max_diff_chars : int
        How many characters of the diff to include in the LLM prompt.
    """

    def __init__(
        self,
        project_root: str | None = None,
        llm_callback: Callable[[str], str] | None = None,
        max_diff_chars: int = 4000,
    ) -> None:
        self._root = str(Path(project_root) if project_root else Path.cwd())
        self._llm = llm_callback
        self._max_diff_chars = max_diff_chars

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        base_branch: str = "main",
        head_branch: str | None = None,
    ) -> PRDescription:
        """
        Generate a PRDescription by comparing *head_branch* against *base_branch*.

        *head_branch* defaults to the currently checked-out branch (HEAD).
        """
        stats = self._gather_stats(base_branch, head_branch)

        if self._llm:
            return self._llm_generate(stats)
        return self._rule_based_generate(stats)

    def format_markdown(self, desc: PRDescription) -> str:
        """Format a PRDescription as a plain Markdown string."""
        parts: list[str] = [f"## {desc.title}", ""]

        if desc.summary:
            parts.append("### Summary")
            for item in desc.summary:
                parts.append(f"- {item}")
            parts.append("")

        if desc.changes:
            parts.append("### Changes")
            for item in desc.changes:
                parts.append(f"- {item}")
            parts.append("")

        if desc.breaking_changes:
            parts.append("### Breaking Changes")
            for item in desc.breaking_changes:
                parts.append(f"- ⚠️ {item}")
            parts.append("")

        if desc.test_plan:
            parts.append("### Test Plan")
            for item in desc.test_plan:
                parts.append(f"- [ ] {item}")
            parts.append("")

        return "\n".join(parts)

    def format_github(self, desc: PRDescription) -> str:
        """Format suitable for `gh pr create --body`."""
        parts: list[str] = ["## Summary", ""]

        for item in desc.summary:
            parts.append(f"- {item}")
        parts.append("")

        if desc.changes:
            parts.append("## Changes")
            for item in desc.changes:
                parts.append(f"- {item}")
            parts.append("")

        if desc.breaking_changes:
            parts.append("## ⚠️ Breaking Changes")
            for item in desc.breaking_changes:
                parts.append(f"- {item}")
            parts.append("")

        parts.append("## Test Plan")
        for item in desc.test_plan:
            parts.append(f"- [ ] {item}")
        parts.append("")

        parts.append(
            "🤖 Generated with [LIDCO](https://github.com/lidco/lidco) PR Description Generator"
        )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _gather_stats(
        self,
        base_branch: str,
        head_branch: str | None,
    ) -> DiffStats:
        head = head_branch or "HEAD"
        ref = f"{base_branch}...{head}"

        # Commits
        raw_log = _run_git(["log", f"--format={_LOG_FMT}", ref], self._root)
        commits = _parse_log(raw_log)

        # File stats
        raw_stat = _run_git(["diff", "--numstat", ref], self._root)
        insertions, deletions, files = _parse_numstat(raw_stat)

        # Short diff for LLM
        raw_diff = _run_git(["diff", "--stat", ref], self._root)
        diff_summary = raw_diff[: self._max_diff_chars]

        # Head branch name
        if not head_branch:
            head_branch = _run_git(
                ["rev-parse", "--abbrev-ref", "HEAD"], self._root
            ).strip() or "HEAD"

        return DiffStats(
            base_branch=base_branch,
            head_branch=head_branch,
            commit_count=len(commits),
            files_changed=files,
            insertions=insertions,
            deletions=deletions,
            commits=commits,
            diff_summary=diff_summary,
        )

    def _llm_generate(self, stats: DiffStats) -> PRDescription:
        prompt = self._build_prompt(stats)
        raw = self._llm(prompt)  # type: ignore[misc]
        return self._parse_llm_response(raw, stats)

    def _rule_based_generate(self, stats: DiffStats) -> PRDescription:
        """Produce a sensible description without an LLM."""
        messages = [c["message"] for c in stats.commits]
        title = messages[0] if messages else f"Changes from {stats.head_branch}"

        summary = [
            f"{stats.commit_count} commit(s) from {stats.head_branch} → {stats.base_branch}",
            f"{len(stats.files_changed)} file(s) changed: "
            f"+{stats.insertions} −{stats.deletions} lines",
        ]

        changes = [f"`{f}`" for f in stats.files_changed[:10]]
        if len(stats.files_changed) > 10:
            changes.append(f"… and {len(stats.files_changed) - 10} more files")

        test_plan = [
            "Run the full test suite",
            "Verify changed functionality manually",
        ]

        # Detect potential breaking changes heuristically
        breaking: list[str] = []
        breaking_keywords = ("BREAKING", "breaking change", "remove", "rename", "delete")
        for msg in messages:
            if any(kw.lower() in msg.lower() for kw in breaking_keywords):
                breaking.append(msg)

        return PRDescription(
            title=title,
            summary=summary,
            changes=changes,
            test_plan=test_plan,
            breaking_changes=breaking,
        )

    def _build_prompt(self, stats: DiffStats) -> str:
        commit_lines = "\n".join(
            f"- {c['hash'][:8]} {c['author']}: {c['message']}"
            for c in stats.commits[:20]
        )
        file_lines = "\n".join(f"- {f}" for f in stats.files_changed[:30])

        return (
            f"You are generating a pull request description for a code review.\n\n"
            f"Branch: {stats.head_branch} → {stats.base_branch}\n"
            f"Commits ({stats.commit_count}):\n{commit_lines}\n\n"
            f"Files changed ({len(stats.files_changed)}, "
            f"+{stats.insertions}/−{stats.deletions}):\n{file_lines}\n\n"
            f"Diff summary:\n{stats.diff_summary}\n\n"
            f"Generate a structured PR description with these sections "
            f"(use the exact markers):\n"
            f"TITLE: <one concise line>\n"
            f"SUMMARY:\n- bullet 1\n- bullet 2\n"
            f"CHANGES:\n- bullet 1\n"
            f"BREAKING CHANGES:\n- bullet (or 'none')\n"
            f"TEST PLAN:\n- [ ] item 1\n"
        )

    def _parse_llm_response(self, raw: str, stats: DiffStats) -> PRDescription:
        """Parse the structured LLM response into a PRDescription."""
        def _extract(header: str) -> list[str]:
            pattern = rf"{re.escape(header)}\s*\n(.*?)(?=\n[A-Z ]+:|$)"
            m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
            if not m:
                return []
            block = m.group(1)
            items = []
            for line in block.splitlines():
                line = re.sub(r"^[-*•\[\] ]+", "", line).strip()
                if line and line.lower() not in ("none", "n/a", ""):
                    items.append(line)
            return items

        title_m = re.search(r"TITLE:\s*(.+)", raw, re.IGNORECASE)
        title = title_m.group(1).strip() if title_m else (
            stats.commits[0]["message"] if stats.commits else "PR changes"
        )

        return PRDescription(
            title=title,
            summary=_extract("SUMMARY:"),
            changes=_extract("CHANGES:"),
            breaking_changes=_extract("BREAKING CHANGES:"),
            test_plan=_extract("TEST PLAN:"),
        )
