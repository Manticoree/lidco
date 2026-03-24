"""Automated PR review — fetches diff, analyzes, posts comments via gh CLI."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "info": 3}


@dataclass
class ReviewComment:
    """A single review comment attached to a file and line."""

    path: str
    line: int
    body: str
    severity: str = "info"  # critical / high / medium / info


@dataclass
class ReviewResult:
    """Aggregated result of a PR review."""

    pr_number: int
    comments: list[ReviewComment] = field(default_factory=list)
    summary: str = ""
    severity_counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    def has_critical(self) -> bool:
        """Return True if any critical issues were found."""
        return self.severity_counts.get("critical", 0) > 0

    def total_issues(self) -> int:
        """Return the total number of issues across all severities."""
        return sum(self.severity_counts.values())


class PRReviewer:
    """Runs heuristic analysis on a PR diff and optionally posts comments."""

    def __init__(
        self,
        post_comments: bool = False,
        max_diff_lines: int = 3000,
    ) -> None:
        self._post_comments = post_comments
        self._max_diff_lines = max_diff_lines

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_diff(self, pr_number: int, repo: str | None = None) -> str | None:
        """Fetch the PR diff using ``gh pr diff``.

        Returns raw diff text or *None* on failure.
        """
        cmd = ["gh", "pr", "diff", str(pr_number)]
        if repo:
            cmd += ["--repo", repo]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                logger.warning("gh pr diff failed: %s", result.stderr.strip())
                return None
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning("Could not fetch PR diff: %s", exc)
            return None

    def fetch_pr_info(
        self, pr_number: int, repo: str | None = None,
    ) -> dict[str, Any]:
        """Fetch PR metadata (title, body, base branch) via ``gh``."""
        cmd = [
            "gh", "pr", "view", str(pr_number),
            "--json", "title,body,baseRefName,headRefName,author",
        ]
        if repo:
            cmd += ["--repo", repo]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not fetch PR info: %s", exc)
        return {}

    def analyze_diff(self, diff_text: str) -> list[ReviewComment]:
        """Run heuristic analysis on a unified diff, return review comments."""
        comments: list[ReviewComment] = []
        if not diff_text:
            return comments

        lines = diff_text.splitlines()
        current_file = ""
        current_line = 0

        for raw_line in lines:
            # Track current file
            if raw_line.startswith("+++ b/"):
                current_file = raw_line[6:].strip()
                current_line = 0
                continue
            if raw_line.startswith("@@ "):
                m = re.search(r"\+(\d+)", raw_line)
                current_line = int(m.group(1)) if m else 0
                continue
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                current_line += 1
                added = raw_line[1:]
                checks = self._check_line(added, current_file, current_line)
                comments.extend(checks)
            elif not raw_line.startswith("-"):
                current_line += 1

        return comments

    def build_summary(
        self, comments: list[ReviewComment],
    ) -> tuple[str, dict[str, int]]:
        """Build a human-readable summary string and severity count dict."""
        counts: dict[str, int] = {}
        for c in comments:
            counts[c.severity] = counts.get(c.severity, 0) + 1

        if not comments:
            return "No issues found.", counts

        parts = []
        for sev in ("critical", "high", "medium", "info"):
            n = counts.get(sev, 0)
            if n:
                parts.append(f"{n} {sev}")
        summary = f"Found {len(comments)} issue(s): " + ", ".join(parts)
        return summary, counts

    def post_comments(
        self,
        pr_number: int,
        comments: list[ReviewComment],
        repo: str | None = None,
    ) -> int:
        """Post review comments via ``gh pr comment``. Returns count posted."""
        posted = 0
        for c in comments:
            if c.severity not in ("critical", "high"):
                continue  # only post critical/high by default
            cmd = [
                "gh", "pr", "comment", str(pr_number),
                "--body",
                f"**[LIDCO {c.severity.upper()}]** `{c.path}:{c.line}`\n\n{c.body}",
            ]
            if repo:
                cmd += ["--repo", repo]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=15,
                )
                if result.returncode == 0:
                    posted += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to post comment: %s", exc)
        return posted

    def review(
        self, pr_number: int, repo: str | None = None,
    ) -> ReviewResult:
        """Full review pipeline: fetch diff, analyze, summarize, optionally post."""
        result = ReviewResult(pr_number=pr_number)

        diff = self.fetch_diff(pr_number, repo)
        if diff is None:
            result.error = f"Could not fetch diff for PR #{pr_number}"
            return result

        # Truncate very large diffs
        diff_lines = diff.splitlines()
        if len(diff_lines) > self._max_diff_lines:
            diff = "\n".join(diff_lines[: self._max_diff_lines])

        comments = self.analyze_diff(diff)
        summary, counts = self.build_summary(comments)
        result.comments = sorted(
            comments, key=lambda c: SEVERITY_ORDER.get(c.severity, 99),
        )
        result.summary = summary
        result.severity_counts = counts

        if self._post_comments and comments:
            self.post_comments(pr_number, comments, repo)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_line(
        self, line: str, path: str, lineno: int,
    ) -> list[ReviewComment]:
        """Heuristic checks on a single added line."""
        found: list[ReviewComment] = []

        # Hardcoded secrets
        secret_patterns = [
            (
                r'(?i)(password|passwd|secret|api_key|apikey|token)\s*=\s*["\'][^"\']{8,}["\']',
                "critical",
                "Possible hardcoded secret. Use environment variables instead.",
            ),
            (
                r"(?i)sk-[a-zA-Z0-9]{20,}",
                "critical",
                "Possible API key in source code.",
            ),
        ]
        for pattern, severity, msg in secret_patterns:
            if re.search(pattern, line):
                found.append(
                    ReviewComment(path=path, line=lineno, body=msg, severity=severity),
                )

        # TODO / FIXME / HACK comments
        if re.search(r"\bTODO\b|\bFIXME\b|\bHACK\b", line):
            found.append(
                ReviewComment(
                    path=path,
                    line=lineno,
                    body="TODO/FIXME/HACK comment in new code. Consider resolving before merging.",
                    severity="info",
                ),
            )

        # Debug prints (skip test files)
        if re.search(r"\bprint\s*\(|console\.log\s*\(", line):
            if "test" not in path.lower():
                found.append(
                    ReviewComment(
                        path=path,
                        line=lineno,
                        body="Debug print/console.log in non-test file.",
                        severity="medium",
                    ),
                )

        # SQL injection risk
        if re.search(r'execute\s*\(\s*["\'].*%s|execute\s*\(\s*f["\']', line):
            found.append(
                ReviewComment(
                    path=path,
                    line=lineno,
                    body="Possible SQL injection: use parameterized queries.",
                    severity="high",
                ),
            )

        return found
