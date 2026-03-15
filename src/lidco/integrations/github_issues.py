"""GitHub Issues integration via the gh CLI — Task 403."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Issue:
    """Structured GitHub issue."""

    number: int
    title: str
    state: str
    body: str
    labels: list[str]
    url: str


class IssueClient:
    """GitHub Issues client wrapping the gh CLI."""

    def list_issues(
        self,
        state: str = "open",
        labels: list[str] | None = None,
        limit: int = 20,
    ) -> list[Issue]:
        """List GitHub issues.

        Args:
            state: Issue state — "open", "closed", or "all".
            labels: Optional label filters.
            limit: Maximum number of issues to return.

        Returns:
            List of Issue dataclass instances.

        Raises:
            RuntimeError: If gh CLI is not installed or returns an error.
        """
        cmd = [
            "gh", "issue", "list",
            "--state", state,
            "--limit", str(limit),
            "--json", "number,title,state,body,labels,url",
        ]
        if labels:
            for label in labels:
                cmd += ["--label", label]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "gh: command not found" in stderr or result.returncode == 127:
                raise RuntimeError(
                    "gh CLI not installed. Install it from https://cli.github.com/"
                )
            raise RuntimeError(stderr or f"gh exited with code {result.returncode}")

        try:
            raw: list[dict] = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not parse gh output: {exc}") from exc

        return [_parse_issue(item) for item in raw]

    def get_issue(self, number: int) -> Issue:
        """Fetch a single issue by number.

        Args:
            number: The issue number.

        Returns:
            Issue dataclass.

        Raises:
            RuntimeError: If gh CLI fails or issue not found.
        """
        cmd = [
            "gh", "issue", "view", str(number),
            "--json", "number,title,state,body,labels,url",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "gh: command not found" in stderr or result.returncode == 127:
                raise RuntimeError(
                    "gh CLI not installed. Install it from https://cli.github.com/"
                )
            raise RuntimeError(stderr or f"gh exited with code {result.returncode}")

        try:
            raw: dict = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not parse gh output: {exc}") from exc

        return _parse_issue(raw)

    def create_issue(
        self,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
    ) -> Issue:
        """Create a new GitHub issue.

        Args:
            title: Issue title.
            body: Issue body/description.
            labels: Optional labels to apply.

        Returns:
            Newly created Issue dataclass.

        Raises:
            RuntimeError: If gh CLI fails.
        """
        cmd = [
            "gh", "issue", "create",
            "--title", title,
            "--body", body,
            "--json", "number,title,state,body,labels,url",
        ]
        if labels:
            for label in labels:
                cmd += ["--label", label]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "gh: command not found" in stderr or result.returncode == 127:
                raise RuntimeError(
                    "gh CLI not installed. Install it from https://cli.github.com/"
                )
            raise RuntimeError(stderr or f"gh exited with code {result.returncode}")

        try:
            raw: dict = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not parse gh output: {exc}") from exc

        return _parse_issue(raw)

    def close_issue(self, number: int) -> bool:
        """Close a GitHub issue.

        Args:
            number: The issue number to close.

        Returns:
            True on success.

        Raises:
            RuntimeError: If gh CLI fails.
        """
        cmd = ["gh", "issue", "close", str(number)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "gh: command not found" in stderr or result.returncode == 127:
                raise RuntimeError(
                    "gh CLI not installed. Install it from https://cli.github.com/"
                )
            raise RuntimeError(stderr or f"gh exited with code {result.returncode}")
        return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_issue(raw: dict) -> Issue:
    """Convert a gh JSON dict to an Issue dataclass."""
    labels_raw = raw.get("labels") or []
    labels: list[str] = []
    for lbl in labels_raw:
        if isinstance(lbl, dict):
            labels.append(lbl.get("name", ""))
        else:
            labels.append(str(lbl))

    return Issue(
        number=int(raw.get("number", 0)),
        title=str(raw.get("title", "")),
        state=str(raw.get("state", "")),
        body=str(raw.get("body") or ""),
        labels=[l for l in labels if l],
        url=str(raw.get("url", "")),
    )
