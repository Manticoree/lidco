"""CI/CD pipeline status integration via the gh CLI — Task 404."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CIRun:
    """Structured CI/CD workflow run."""

    run_id: str
    name: str
    status: str
    conclusion: str
    url: str
    branch: str
    created_at: str = ""
    updated_at: str = ""


class CIClient:
    """CI/CD status client wrapping the gh CLI."""

    def get_current_branch_status(self, limit: int = 5) -> list[CIRun]:
        """Fetch the latest workflow runs for the current branch.

        Args:
            limit: Maximum number of runs to return (default 5).

        Returns:
            List of CIRun dataclass instances.

        Raises:
            RuntimeError: If gh CLI is not installed or returns an error.
        """
        branch = self._get_current_branch()
        return self.get_branch_status(branch, limit=limit)

    def get_branch_status(self, branch: str, limit: int = 5) -> list[CIRun]:
        """Fetch the latest workflow runs for a specific branch.

        Args:
            branch: Branch name to query.
            limit: Maximum number of runs to return.

        Returns:
            List of CIRun dataclass instances.

        Raises:
            RuntimeError: If gh CLI is not installed or returns an error.
        """
        cmd = [
            "gh", "run", "list",
            "--branch", branch,
            "--limit", str(limit),
            "--json", "databaseId,name,status,conclusion,url,headBranch,createdAt,updatedAt",
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
            raw: list[dict] = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not parse gh output: {exc}") from exc

        return [_parse_run(item) for item in raw]

    def get_run(self, run_id: str) -> CIRun:
        """Fetch details for a single workflow run.

        Args:
            run_id: The workflow run ID.

        Returns:
            CIRun dataclass.

        Raises:
            RuntimeError: If gh CLI fails or run not found.
        """
        cmd = [
            "gh", "run", "view", str(run_id),
            "--json", "databaseId,name,status,conclusion,url,headBranch,createdAt,updatedAt",
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

        return _parse_run(raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_current_branch() -> str:
        """Return current git branch name."""
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return "main"
        return result.stdout.strip() or "main"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _parse_run(raw: dict) -> CIRun:
    """Convert a gh JSON dict to a CIRun dataclass."""
    return CIRun(
        run_id=str(raw.get("databaseId", "")),
        name=str(raw.get("name", "")),
        status=str(raw.get("status", "")),
        conclusion=str(raw.get("conclusion") or ""),
        url=str(raw.get("url", "")),
        branch=str(raw.get("headBranch", "")),
        created_at=str(raw.get("createdAt", "")),
        updated_at=str(raw.get("updatedAt", "")),
    )
