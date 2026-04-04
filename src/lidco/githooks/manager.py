"""HookManagerV2 — install, uninstall, run, and list git hooks.

Manages hooks in a configurable hooks directory (defaults to .git/hooks/).
Supports parallel execution and typed hook enums.
"""

from __future__ import annotations

import enum
import os
import stat
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence


class HookType(enum.Enum):
    """Standard git hook types."""

    PRE_COMMIT = "pre-commit"
    PRE_PUSH = "pre-push"
    COMMIT_MSG = "commit-msg"
    POST_COMMIT = "post-commit"


@dataclass(frozen=True)
class HookResult:
    """Result of running a single hook."""

    hook_type: HookType
    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration: float = 0.0


class HookManagerV2:
    """Manage git hooks: install, uninstall, list, run, parallel_run."""

    def __init__(self, hooks_dir: str | Path | None = None) -> None:
        if hooks_dir is None:
            hooks_dir = Path(".git/hooks")
        self._hooks_dir = Path(hooks_dir)
        self._hooks_dir.mkdir(parents=True, exist_ok=True)

    @property
    def hooks_dir(self) -> Path:
        return self._hooks_dir

    # ------------------------------------------------------------------
    # Install / Uninstall
    # ------------------------------------------------------------------

    def install(self, hook_type: HookType, script: str) -> bool:
        """Write *script* as the hook file and make it executable. Returns True."""
        path = self._hooks_dir / hook_type.value
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return True

    def uninstall(self, hook_type: HookType) -> bool:
        """Remove the hook file. Returns False if it did not exist."""
        path = self._hooks_dir / hook_type.value
        if not path.exists():
            return False
        path.unlink()
        return True

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_installed(self) -> List[HookType]:
        """Return list of HookType values that are currently installed."""
        result: list[HookType] = []
        for ht in HookType:
            if (self._hooks_dir / ht.value).exists():
                result.append(ht)
        return result

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, hook_type: HookType, args: Sequence[str] = ()) -> HookResult:
        """Run a single hook synchronously, returning a *HookResult*."""
        path = self._hooks_dir / hook_type.value
        if not path.exists():
            return HookResult(
                hook_type=hook_type,
                success=False,
                exit_code=-1,
                stderr="Hook not installed.",
            )
        start = time.monotonic()
        try:
            proc = subprocess.run(
                [str(path), *args],
                capture_output=True,
                text=True,
                timeout=60,
            )
            elapsed = time.monotonic() - start
            return HookResult(
                hook_type=hook_type,
                success=proc.returncode == 0,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return HookResult(
                hook_type=hook_type,
                success=False,
                exit_code=-2,
                stderr="Hook timed out.",
                duration=elapsed,
            )
        except OSError as exc:
            elapsed = time.monotonic() - start
            return HookResult(
                hook_type=hook_type,
                success=False,
                exit_code=-3,
                stderr=str(exc),
                duration=elapsed,
            )

    def parallel_run(self, hooks: Sequence[HookType], args: Sequence[str] = ()) -> List[HookResult]:
        """Run multiple hooks in parallel using a thread pool."""
        if not hooks:
            return []
        results: dict[HookType, HookResult] = {}
        with ThreadPoolExecutor(max_workers=min(len(hooks), 4)) as pool:
            futures = {pool.submit(self.run, ht, args): ht for ht in hooks}
            for future in as_completed(futures):
                ht = futures[future]
                results[ht] = future.result()
        # Return in the same order as input
        return [results[ht] for ht in hooks]
