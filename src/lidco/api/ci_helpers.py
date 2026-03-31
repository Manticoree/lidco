"""CI/CD integration helpers — detect environment, format output — Q171."""
from __future__ import annotations

import os
from dataclasses import dataclass

from lidco.api.library import LidcoResult


@dataclass
class CIEnvironment:
    """Detected CI environment."""

    provider: str  # github, gitlab, local
    branch: str
    commit: str
    pr_number: int | None
    repo: str


def detect_ci() -> CIEnvironment:
    """Detect CI environment from well-known env vars."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        pr_raw = os.environ.get("GITHUB_PR_NUMBER", "")
        pr_number: int | None = int(pr_raw) if pr_raw.isdigit() else None
        return CIEnvironment(
            provider="github",
            branch=os.environ.get("GITHUB_REF_NAME", ""),
            commit=os.environ.get("GITHUB_SHA", ""),
            pr_number=pr_number,
            repo=os.environ.get("GITHUB_REPOSITORY", ""),
        )
    if os.environ.get("GITLAB_CI") == "true":
        mr_raw = os.environ.get("CI_MERGE_REQUEST_IID", "")
        mr_number: int | None = int(mr_raw) if mr_raw.isdigit() else None
        return CIEnvironment(
            provider="gitlab",
            branch=os.environ.get("CI_COMMIT_BRANCH", ""),
            commit=os.environ.get("CI_COMMIT_SHA", ""),
            pr_number=mr_number,
            repo=os.environ.get("CI_PROJECT_PATH", ""),
        )
    return CIEnvironment(
        provider="local",
        branch="",
        commit="",
        pr_number=None,
        repo="",
    )


def format_ci_output(result: LidcoResult, env: CIEnvironment) -> str:
    """Format a result for CI log output."""
    status = "PASS" if result.success else "FAIL"
    lines = [
        f"[{env.provider.upper()}] {status}",
        f"Branch: {env.branch}" if env.branch else "",
        f"Commit: {env.commit[:8]}" if env.commit else "",
        f"Tokens: {result.tokens_used}",
        f"Duration: {result.duration:.2f}s",
    ]
    if result.error:
        lines.append(f"Error: {result.error}")
    if result.files_changed:
        lines.append(f"Files changed: {', '.join(result.files_changed)}")
    return "\n".join(line for line in lines if line)


def github_pr_comment(result: LidcoResult) -> str:
    """Generate a GitHub PR comment in markdown."""
    icon = "white_check_mark" if result.success else "x"
    lines = [
        f"## :{icon}: LIDCO Result",
        "",
        f"**Status:** {'Success' if result.success else 'Failure'}",
        f"**Tokens used:** {result.tokens_used}",
        f"**Duration:** {result.duration:.2f}s",
    ]
    if result.error:
        lines.extend(["", f"**Error:** {result.error}"])
    if result.output:
        lines.extend(["", "### Output", "", f"```\n{result.output}\n```"])
    if result.files_changed:
        lines.extend(["", "### Files Changed", ""])
        for f in result.files_changed:
            lines.append(f"- `{f}`")
    return "\n".join(lines)


def gitlab_mr_note(result: LidcoResult) -> str:
    """Generate a GitLab MR note in markdown."""
    icon = ":white_check_mark:" if result.success else ":x:"
    lines = [
        f"## {icon} LIDCO Result",
        "",
        f"| Key | Value |",
        f"| --- | --- |",
        f"| Status | {'Success' if result.success else 'Failure'} |",
        f"| Tokens | {result.tokens_used} |",
        f"| Duration | {result.duration:.2f}s |",
    ]
    if result.error:
        lines.append(f"| Error | {result.error} |")
    if result.output:
        lines.extend(["", "### Output", "", f"```\n{result.output}\n```"])
    if result.files_changed:
        lines.extend(["", "### Files Changed", ""])
        for f in result.files_changed:
            lines.append(f"- `{f}`")
    return "\n".join(lines)


def exit_code(result: LidcoResult) -> int:
    """Return process exit code: 0 for success, 1 for failure."""
    return 0 if result.success else 1
