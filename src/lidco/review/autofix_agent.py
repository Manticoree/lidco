"""AutofixAgent — spawns isolated agent to fix a review comment."""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class FixProposal:
    comment_id: str
    patch: str  # unified diff
    test_result: str
    confidence: float
    applied: bool = False


class AutofixAgent:
    """For each critical/high review comment, attempt an automated fix."""

    def __init__(
        self,
        project_dir: Path | None = None,
        test_cmd: str = "python -m pytest -q --tb=no",
        fix_fn: Callable[[str, str], str] | None = None,
    ) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._test_cmd = test_cmd
        # fix_fn(comment_body, file_content) -> patched_content  (injected for testing)
        self._fix_fn = fix_fn

    def fix(self, comment_id: str, comment_body: str, file_path: str | None = None) -> FixProposal | None:
        """Attempt to fix a comment. Returns FixProposal or None."""
        if self._fix_fn is None:
            return None

        original_content = ""
        if file_path:
            abs_path = self._project_dir / file_path
            if abs_path.is_file():
                original_content = abs_path.read_text(encoding="utf-8", errors="replace")

        try:
            fixed_content = self._fix_fn(comment_body, original_content)
        except Exception:
            return None

        if not fixed_content or fixed_content == original_content:
            return None

        patch = _make_patch(file_path or "unknown", original_content, fixed_content)
        test_result = self._run_tests()
        confidence = 0.8 if "passed" in test_result.lower() else 0.4

        return FixProposal(
            comment_id=comment_id,
            patch=patch,
            test_result=test_result,
            confidence=confidence,
        )

    def _run_tests(self) -> str:
        try:
            result = subprocess.run(
                self._test_cmd,
                shell=True,
                cwd=self._project_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.stdout[-500:] if result.stdout else result.stderr[-500:]
        except subprocess.TimeoutExpired:
            return "timeout"
        except OSError as exc:
            return str(exc)


def _make_patch(file_path: str, original: str, fixed: str) -> str:
    import difflib
    lines = list(difflib.unified_diff(
        original.splitlines(keepends=True),
        fixed.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    ))
    return "".join(lines)
