"""Guard against applying edits to files that have changed since last read."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import time


@dataclass
class StaleCheckResult:
    file_path: str
    is_stale: bool
    read_mtime: float | None
    current_mtime: float | None
    message: str


@dataclass
class GuardConfig:
    enabled: bool = True
    auto_rebase: bool = False  # If True, auto-re-read; if False, abort


class StaleEditGuard:
    def __init__(self, config: GuardConfig | None = None):
        self._config = config or GuardConfig()
        self._read_times: dict[str, float] = {}  # file_path -> mtime at read time

    @property
    def config(self) -> GuardConfig:
        return self._config

    def record_read(self, file_path: str, mtime: float) -> None:
        """Record when a file was last read and its mtime."""
        self._read_times = {**self._read_times, file_path: mtime}

    def check(self, file_path: str) -> StaleCheckResult:
        """Check if a file is stale (modified since last read)."""
        if not self._config.enabled:
            return StaleCheckResult(
                file_path=file_path, is_stale=False,
                read_mtime=None, current_mtime=None,
                message="Stale check disabled",
            )

        read_mtime = self._read_times.get(file_path)
        if read_mtime is None:
            return StaleCheckResult(
                file_path=file_path, is_stale=False,
                read_mtime=None, current_mtime=None,
                message="File not previously read — no staleness check",
            )

        try:
            current_mtime = os.path.getmtime(file_path)
        except OSError:
            return StaleCheckResult(
                file_path=file_path, is_stale=True,
                read_mtime=read_mtime, current_mtime=None,
                message="File no longer exists — cannot apply edit",
            )

        if current_mtime != read_mtime:
            return StaleCheckResult(
                file_path=file_path, is_stale=True,
                read_mtime=read_mtime, current_mtime=current_mtime,
                message=f"File modified since last read (read: {read_mtime}, current: {current_mtime})",
            )

        return StaleCheckResult(
            file_path=file_path, is_stale=False,
            read_mtime=read_mtime, current_mtime=current_mtime,
            message="File is up to date",
        )

    def check_multiple(self, file_paths: list[str]) -> list[StaleCheckResult]:
        """Check multiple files for staleness."""
        return [self.check(fp) for fp in file_paths]

    def has_stale_files(self, file_paths: list[str]) -> bool:
        """Quick check if any files are stale."""
        return any(r.is_stale for r in self.check_multiple(file_paths))

    def clear(self) -> None:
        """Clear all read records."""
        self._read_times = {}

    def forget(self, file_path: str) -> None:
        """Remove read record for a specific file."""
        new_times = dict(self._read_times)
        new_times.pop(file_path, None)
        self._read_times = new_times
