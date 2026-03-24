"""GHPoster — post inline review comments to GitHub PRs via gh CLI."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReviewComment:
    path: str
    line: int
    body: str
    severity: str = "info"  # critical | high | medium | info

    def content_hash(self) -> str:
        data = f"{self.path}:{self.line}:{self.body}"
        return hashlib.md5(data.encode()).hexdigest()


@dataclass
class PostResult:
    success: bool
    posted_count: int
    skipped_count: int
    error: str | None = None


class GHPoster:
    """Post review comments to GitHub PRs using gh CLI."""

    def __init__(self, repo: str | None = None, project_dir: Path | None = None) -> None:
        self._repo = repo
        self._project_dir = project_dir or Path.cwd()
        self._posted_hashes: set[str] = set()

    def post_review(
        self,
        pr_number: int | str,
        comments: list[ReviewComment],
        summary: str = "",
    ) -> PostResult:
        """Post comments to the PR. Deduplicates by content hash."""
        posted = 0
        skipped = 0

        for comment in comments:
            h = comment.content_hash()
            if h in self._posted_hashes:
                skipped += 1
                continue

            ok = self._post_inline(pr_number, comment)
            if ok:
                self._posted_hashes.add(h)
                posted += 1
            else:
                skipped += 1

        if summary:
            self._post_summary(pr_number, summary)

        return PostResult(success=True, posted_count=posted, skipped_count=skipped)

    def _post_inline(self, pr_number: int | str, comment: ReviewComment) -> bool:
        cmd = ["gh", "pr", "review", str(pr_number), "--comment", "-b", comment.body]
        if self._repo:
            cmd += ["-R", self._repo]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=self._project_dir)
            return result.returncode == 0
        except Exception:
            return False

    def _post_summary(self, pr_number: int | str, summary: str) -> bool:
        cmd = ["gh", "pr", "comment", str(pr_number), "-b", summary]
        if self._repo:
            cmd += ["-R", self._repo]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=self._project_dir)
            return result.returncode == 0
        except Exception:
            return False

    def clear_cache(self) -> None:
        self._posted_hashes.clear()
