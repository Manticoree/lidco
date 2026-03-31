"""System info collector — Task 850."""

from __future__ import annotations

import os
import platform
import sys
import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class SystemReport:
    """Snapshot of the runtime environment."""

    python_version: str
    platform: str
    architecture: str
    cwd: str
    pid: int
    cpu_count: Optional[int]
    encoding: str
    timezone: str


class SystemInfo:
    """Collect and format system information."""

    def __init__(
        self,
        *,
        _platform_fn: Callable[[], str] | None = None,
        _architecture_fn: Callable[[], tuple[str, str]] | None = None,
        _cwd_fn: Callable[[], str] | None = None,
        _pid_fn: Callable[[], int] | None = None,
        _cpu_count_fn: Callable[[], Optional[int]] | None = None,
        _encoding_fn: Callable[[], str] | None = None,
        _timezone_fn: Callable[[], str] | None = None,
        _python_version_fn: Callable[[], str] | None = None,
    ) -> None:
        self._platform_fn = _platform_fn or platform.platform
        self._architecture_fn = _architecture_fn or platform.architecture
        self._cwd_fn = _cwd_fn or os.getcwd
        self._pid_fn = _pid_fn or (lambda: os.getpid())
        self._cpu_count_fn = _cpu_count_fn or os.cpu_count
        self._encoding_fn = _encoding_fn or sys.getdefaultencoding
        self._timezone_fn = _timezone_fn or (lambda: time.tzname[0])
        self._python_version_fn = _python_version_fn or (lambda: sys.version)

    def collect(self) -> SystemReport:
        """Gather all system information into a report."""
        arch_tuple = self._architecture_fn()
        return SystemReport(
            python_version=self._python_version_fn(),
            platform=self._platform_fn(),
            architecture=arch_tuple[0],
            cwd=self._cwd_fn(),
            pid=self._pid_fn(),
            cpu_count=self._cpu_count_fn(),
            encoding=self._encoding_fn(),
            timezone=self._timezone_fn(),
        )

    @staticmethod
    def format_report(report: SystemReport) -> str:
        """Human-readable report."""
        lines = [
            "System Report",
            f"  Python : {report.python_version}",
            f"  Platform : {report.platform}",
            f"  Arch : {report.architecture}",
            f"  CWD : {report.cwd}",
            f"  PID : {report.pid}",
            f"  CPUs : {report.cpu_count}",
            f"  Encoding : {report.encoding}",
            f"  Timezone : {report.timezone}",
        ]
        return "\n".join(lines)

    @staticmethod
    def as_dict(report: SystemReport) -> dict:
        """Convert report to a plain dict."""
        return {
            "python_version": report.python_version,
            "platform": report.platform,
            "architecture": report.architecture,
            "cwd": report.cwd,
            "pid": report.pid,
            "cpu_count": report.cpu_count,
            "encoding": report.encoding,
            "timezone": report.timezone,
        }

    def check_compatibility(self) -> list[str]:
        """Return a list of compatibility warnings (empty if all good)."""
        warnings: list[str] = []
        vi = sys.version_info
        if vi < (3, 10):
            warnings.append(f"Python {vi.major}.{vi.minor} < 3.10 — may not be supported")
        cpu = self._cpu_count_fn()
        if cpu is not None and cpu < 2:
            warnings.append("Single CPU core detected — parallel operations will be slow")
        return warnings
