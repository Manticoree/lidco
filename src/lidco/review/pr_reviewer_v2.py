"""PRReviewAgentV2 — structured PR review with GitHub comment threading."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ReviewComment:
    path: str
    line: int
    severity: str  # "critical" | "warning" | "suggestion"
    body: str
    suggestion: str = ""  # optional code suggestion block


@dataclass
class PRReviewResult:
    pr_number: int
    summary: str
    comments: list[ReviewComment]
    verdict: str  # "approve" | "request_changes" | "comment"


_SEVERITY_BADGE = {
    "critical": "🔴 **CRITICAL**",
    "warning": "🟡 **WARNING**",
    "suggestion": "🟢 **SUGGESTION**",
}

_DEFAULT_REVIEW_PROMPT = """\
You are a senior code reviewer. Review the following pull request diff and return a JSON object with this structure:
{
  "summary": "<one paragraph summary>",
  "verdict": "approve" | "request_changes" | "comment",
  "comments": [
    {"path": "<file>", "line": <int>, "severity": "critical"|"warning"|"suggestion", "body": "<text>", "suggestion": "<optional code>"}
  ]
}

Return ONLY the JSON, no markdown fences.

Pull Request Diff:
"""


class PRReviewAgentV2:
    """Review a PR and post structured GitHub comments."""

    def __init__(
        self,
        llm_fn: Callable[[str], str] | None = None,
        gh_token: str = "",
    ) -> None:
        self._llm_fn = llm_fn
        self._gh_token = gh_token

    # ------------------------------------------------------------------
    # Review
    # ------------------------------------------------------------------

    def review(self, repo: str, pr_number: int) -> PRReviewResult:
        """Fetch PR diff from GitHub and run LLM review."""
        diff = self._fetch_diff(repo, pr_number)
        return self._run_review(pr_number, diff)

    def _fetch_diff(self, repo: str, pr_number: int) -> str:
        """Fetch unified diff via GitHub API. Returns '' on error."""
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
        headers = {
            "Accept": "application/vnd.github.v3.diff",
            "User-Agent": "lidco-pr-reviewer/1.0",
        }
        if self._gh_token:
            headers["Authorization"] = f"token {self._gh_token}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _run_review(self, pr_number: int, diff: str) -> PRReviewResult:
        """Call LLM and parse response into PRReviewResult."""
        if self._llm_fn is None or not diff:
            return PRReviewResult(
                pr_number=pr_number,
                summary="No diff available or LLM not configured.",
                comments=[],
                verdict="comment",
            )

        prompt = _DEFAULT_REVIEW_PROMPT + diff[:8000]  # trim to avoid token overflow
        try:
            raw = self._llm_fn(prompt)
        except Exception as exc:
            return PRReviewResult(
                pr_number=pr_number,
                summary=f"LLM error: {exc}",
                comments=[],
                verdict="comment",
            )

        return self._parse_response(pr_number, raw)

    def _parse_response(self, pr_number: int, raw: str) -> PRReviewResult:
        """Parse LLM JSON response into PRReviewResult."""
        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end <= start:
            return PRReviewResult(
                pr_number=pr_number,
                summary=raw,
                comments=[],
                verdict="comment",
            )
        try:
            data = json.loads(raw[start:end])
            comments = [
                ReviewComment(
                    path=c.get("path", ""),
                    line=int(c.get("line", 1)),
                    severity=c.get("severity", "suggestion"),
                    body=c.get("body", ""),
                    suggestion=c.get("suggestion", ""),
                )
                for c in data.get("comments", [])
            ]
            return PRReviewResult(
                pr_number=pr_number,
                summary=data.get("summary", ""),
                comments=comments,
                verdict=data.get("verdict", "comment"),
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return PRReviewResult(
                pr_number=pr_number,
                summary=raw,
                comments=[],
                verdict="comment",
            )

    # ------------------------------------------------------------------
    # Format
    # ------------------------------------------------------------------

    def format_review(self, result: PRReviewResult) -> str:
        """Format result as a Markdown review."""
        verdict_emoji = {"approve": "✅", "request_changes": "❌", "comment": "💬"}
        emoji = verdict_emoji.get(result.verdict, "💬")

        lines = [
            f"## PR #{result.pr_number} Review {emoji}",
            "",
            f"**Verdict:** {result.verdict.replace('_', ' ').title()}",
            "",
            "### Summary",
            result.summary,
        ]

        if result.comments:
            lines += ["", "### Comments"]
            for c in result.comments:
                badge = _SEVERITY_BADGE.get(c.severity, c.severity)
                lines.append(f"\n**{c.path}:{c.line}** {badge}")
                lines.append(c.body)
                if c.suggestion:
                    lines.append(f"\n```suggestion\n{c.suggestion}\n```")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Post to GitHub
    # ------------------------------------------------------------------

    def post_review(self, repo: str, pr_number: int, result: PRReviewResult) -> bool:
        """POST review to GitHub pull request review API. Returns True on success."""
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "lidco-pr-reviewer/1.0",
        }
        if self._gh_token:
            headers["Authorization"] = f"token {self._gh_token}"

        # Build line comments for GitHub review API
        comments = []
        for c in result.comments:
            entry: dict = {
                "path": c.path,
                "line": c.line,
                "side": "RIGHT",
                "body": f"{_SEVERITY_BADGE.get(c.severity, c.severity)}\n\n{c.body}",
            }
            if c.suggestion:
                entry["body"] += f"\n\n```suggestion\n{c.suggestion}\n```"
            comments.append(entry)

        payload = json.dumps({
            "body": result.summary,
            "event": {
                "approve": "APPROVE",
                "request_changes": "REQUEST_CHANGES",
                "comment": "COMMENT",
            }.get(result.verdict, "COMMENT"),
            "comments": comments,
        }).encode()

        try:
            req = urllib.request.Request(
                url, data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=15):
                return True
        except Exception:
            return False
