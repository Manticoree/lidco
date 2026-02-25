"""GitHub PR context tool — fetches PR metadata and diff via the gh CLI."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from lidco.tools.base import BaseTool, ToolParameter, ToolPermission, ToolResult

logger = logging.getLogger(__name__)

_MAX_DIFF_CHARS = 6_000
_MAX_BODY_CHARS = 2_000
_MAX_COMMENT_CHARS = 500
_MAX_COMMENTS = 10


class GHPRTool(BaseTool):
    """Fetch GitHub PR context (title, description, changed files, comments, diff)
    via the ``gh`` CLI and return it as a formatted Markdown block suitable for
    injection into agent context.

    Requires the ``gh`` CLI to be authenticated:
        ``gh auth login``
    """

    @property
    def name(self) -> str:
        return "gh_pr"

    @property
    def description(self) -> str:
        return (
            "Fetch GitHub PR context via the gh CLI. "
            "Returns PR title, description, changed files, comments, and optional diff "
            "formatted as Markdown for injection into agent context."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="number",
                type="string",
                description="PR number (e.g. '123') or branch name.",
            ),
            ToolParameter(
                name="include_diff",
                type="boolean",
                description=(
                    "Append the unified diff to the output "
                    f"(first {_MAX_DIFF_CHARS} chars). Defaults to True."
                ),
                required=False,
                default=True,
            ),
        ]

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.AUTO

    async def _run(self, number: str = "", include_diff: bool = True, **_: Any) -> ToolResult:
        if not number:
            return ToolResult(output="", success=False, error="PR number is required.")

        pr_data, fetch_error = await _fetch_pr_metadata(str(number))
        if pr_data is None:
            return ToolResult(output="", success=False, error=fetch_error or "Failed to fetch PR.")

        output = _format_pr_context(pr_data)

        if include_diff:
            diff_text = await _fetch_pr_diff(str(number))
            if diff_text:
                truncated = diff_text[:_MAX_DIFF_CHARS]
                suffix = "\n... (diff truncated)" if len(diff_text) > _MAX_DIFF_CHARS else ""
                output += f"\n\n### Unified Diff\n\n```diff\n{truncated}\n```{suffix}"

        return ToolResult(
            output=output,
            success=True,
            metadata={
                "number": pr_data.get("number", number),
                "title": pr_data.get("title", ""),
                "state": pr_data.get("state", ""),
                "branch": pr_data.get("headRefName", ""),
                "base": pr_data.get("baseRefName", ""),
                "files_count": len(pr_data.get("files", [])),
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0),
            },
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch_pr_metadata(number: str) -> tuple[dict | None, str | None]:
    """Run ``gh pr view`` and return (parsed_dict, error_message)."""
    fields = "title,body,files,comments,state,headRefName,baseRefName,additions,deletions,number"
    cmd = ["gh", "pr", "view", number, "--json", fields]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
    except FileNotFoundError:
        return None, "gh CLI not installed. Install it from https://cli.github.com/"
    except asyncio.TimeoutError:
        return None, "gh CLI timed out after 30s."
    except Exception as exc:
        return None, f"gh CLI error: {exc}"

    if process.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        return None, stderr_text or f"gh CLI exited with code {process.returncode}."

    try:
        data: dict = json.loads(stdout.decode("utf-8", errors="replace"))
        return data, None
    except json.JSONDecodeError as exc:
        return None, f"Could not parse gh output as JSON: {exc}"


async def _fetch_pr_diff(number: str) -> str:
    """Run ``gh pr diff`` and return the diff text (empty string on failure)."""
    try:
        process = await asyncio.create_subprocess_exec(
            "gh", "pr", "diff", number,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        if process.returncode == 0:
            return stdout.decode("utf-8", errors="replace")
    except Exception as exc:
        logger.debug("gh pr diff failed for PR #%s: %s", number, exc)
    return ""


def _format_pr_context(pr: dict) -> str:
    """Format a ``gh pr view --json`` dict into a human-readable Markdown block."""
    number = pr.get("number", "?")
    title = pr.get("title", "")
    state = pr.get("state", "")
    head = pr.get("headRefName", "")
    base = pr.get("baseRefName", "main")
    additions = pr.get("additions", 0)
    deletions = pr.get("deletions", 0)
    files: list[dict] = pr.get("files", [])
    comments: list[dict] = pr.get("comments", [])
    body: str = (pr.get("body") or "").strip()

    lines: list[str] = [
        f"## PR #{number}: {title}",
        "",
        f"**Branch:** `{head}` → `{base}`  |  **State:** {state}  |  "
        f"**Changes:** +{additions} −{deletions} across {len(files)} file{'s' if len(files) != 1 else ''}",
    ]

    # Description
    if body:
        truncated_body = body[:_MAX_BODY_CHARS]
        if len(body) > _MAX_BODY_CHARS:
            truncated_body += "\n... (description truncated)"
        lines += ["", "### Description", "", truncated_body]

    # Changed files
    if files:
        lines += ["", "### Changed Files", ""]
        for f in files:
            path = f.get("path", "?")
            adds = f.get("additions", 0)
            dels = f.get("deletions", 0)
            status = f.get("status", "modified")
            lines.append(f"- `{path}` (+{adds}, −{dels}, {status})")

    # Comments
    if comments:
        shown = comments[:_MAX_COMMENTS]
        lines += ["", f"### Comments ({len(comments)})", ""]
        for c in shown:
            author = (c.get("author") or {}).get("login", "unknown")
            created = c.get("createdAt", "")[:10]  # date only
            body_text = (c.get("body") or "").strip()[:_MAX_COMMENT_CHARS]
            if len(c.get("body", "")) > _MAX_COMMENT_CHARS:
                body_text += "..."
            lines += [f"**@{author}** ({created}):", f"> {body_text}", ""]

    return "\n".join(lines)
