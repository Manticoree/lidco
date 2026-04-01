"""System health checks -- Python, git, OS, dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import platform
import shutil
import sys


class CheckStatus(str, Enum):
    """Status of a single health check."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class CheckResult:
    """Result of a single health check."""

    name: str
    status: CheckStatus
    message: str = ""
    detail: str = ""


class SystemChecker:
    """Run system-level health checks."""

    def __init__(self) -> None:
        pass

    def check_python(self) -> CheckResult:
        """Check Python version >= 3.10."""
        vi = sys.version_info
        version_str = f"{vi.major}.{vi.minor}.{vi.micro}"
        if (vi.major, vi.minor) >= (3, 10):
            return CheckResult(
                name="Python",
                status=CheckStatus.PASS,
                message=f"Python {version_str}",
            )
        return CheckResult(
            name="Python",
            status=CheckStatus.FAIL,
            message=f"Python {version_str} < 3.10",
            detail="Upgrade to Python 3.10 or later.",
        )

    def check_git(self) -> CheckResult:
        """Check git is available in PATH."""
        if shutil.which("git") is not None:
            return CheckResult(
                name="git",
                status=CheckStatus.PASS,
                message="git found",
            )
        return CheckResult(
            name="git",
            status=CheckStatus.FAIL,
            message="git not found",
            detail="Install git: https://git-scm.com",
        )

    def check_gh_cli(self) -> CheckResult:
        """Check GitHub CLI is available in PATH."""
        if shutil.which("gh") is not None:
            return CheckResult(
                name="gh CLI",
                status=CheckStatus.PASS,
                message="gh CLI found",
            )
        return CheckResult(
            name="gh CLI",
            status=CheckStatus.FAIL,
            message="gh CLI not found",
            detail="Install gh: https://cli.github.com",
        )

    def check_os(self) -> CheckResult:
        """Report OS platform, detect WSL and Docker."""
        plat = platform.system()
        tags: list[str] = [plat]

        # Detect WSL
        try:
            with open("/proc/version", "r") as fh:
                content = fh.read().lower()
            if "microsoft" in content or "wsl" in content:
                tags.append("WSL")
        except (OSError, FileNotFoundError):
            pass

        # Detect Docker
        if os.path.exists("/.dockerenv"):
            tags.append("Docker")

        label = " + ".join(tags)
        return CheckResult(
            name="OS",
            status=CheckStatus.PASS,
            message=label,
        )

    def check_disk_space(self, path: str = ".") -> CheckResult:
        """Check free disk space; WARN if < 1 GB."""
        try:
            usage = shutil.disk_usage(path)
        except OSError as exc:
            return CheckResult(
                name="Disk",
                status=CheckStatus.SKIP,
                message="Cannot read disk usage",
                detail=str(exc),
            )

        free_gb = usage.free / (1024 ** 3)
        if free_gb >= 1.0:
            return CheckResult(
                name="Disk",
                status=CheckStatus.PASS,
                message=f"{free_gb:.1f} GB free",
            )
        return CheckResult(
            name="Disk",
            status=CheckStatus.WARN,
            message=f"{free_gb:.2f} GB free (< 1 GB)",
            detail="Low disk space may cause issues.",
        )

    def run_all(self) -> list[CheckResult]:
        """Run every check and return results."""
        return [
            self.check_python(),
            self.check_git(),
            self.check_gh_cli(),
            self.check_os(),
            self.check_disk_space(),
        ]

    def summary(self, results: list[CheckResult]) -> str:
        """One-line summary of all results."""
        _markers = {
            CheckStatus.PASS: "[PASS]",
            CheckStatus.WARN: "[WARN]",
            CheckStatus.FAIL: "[FAIL]",
            CheckStatus.SKIP: "[SKIP]",
        }
        parts = [f"{_markers[r.status]} {r.message}" for r in results]
        return " | ".join(parts)
