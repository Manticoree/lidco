"""Environment checker — Task 847."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class EnvCheck:
    """Result of a single environment check."""

    name: str
    status: str  # "ok" | "warning" | "error"
    value: Optional[str]
    message: str


class EnvironmentChecker:
    """Run environment checks with injectable OS helpers for testability."""

    def __init__(
        self,
        *,
        _getenv: Callable[[str], Optional[str]] | None = None,
        _exists: Callable[[str], bool] | None = None,
        _isdir: Callable[[str], bool] | None = None,
        _access: Callable[[str, int], bool] | None = None,
    ) -> None:
        self._getenv = _getenv or os.environ.get
        self._exists = _exists or os.path.exists
        self._isdir = _isdir or os.path.isdir
        self._access = _access or os.access
        self._custom_checks: list[tuple[str, Callable[[], EnvCheck]]] = []
        self._results: list[EnvCheck] = []

    # ── built-in checks ──────────────────────────────────────────────

    def check_python_version(self, min_version: str = "3.10") -> EnvCheck:
        """Check that the running Python meets *min_version*."""
        current = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        cur_tuple = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
        parts = min_version.split(".")
        min_tuple = tuple(int(p) for p in parts)
        if cur_tuple >= min_tuple:
            return EnvCheck("python_version", "ok", current, f"Python {current} >= {min_version}")
        return EnvCheck(
            "python_version",
            "error",
            current,
            f"Python {current} < {min_version}",
        )

    def check_env_var(self, name: str, required: bool = True) -> EnvCheck:
        """Check whether an environment variable is set."""
        val = self._getenv(name)
        if val:
            return EnvCheck(name, "ok", val, f"{name} is set")
        if required:
            return EnvCheck(name, "error", None, f"{name} is not set (required)")
        return EnvCheck(name, "warning", None, f"{name} is not set (optional)")

    def check_directory(self, path: str, writable: bool = False) -> EnvCheck:
        """Check that *path* exists and is a directory (optionally writable)."""
        if not self._exists(path):
            return EnvCheck(f"dir:{path}", "error", None, f"{path} does not exist")
        if not self._isdir(path):
            return EnvCheck(f"dir:{path}", "error", None, f"{path} is not a directory")
        if writable and not self._access(path, os.W_OK):
            return EnvCheck(f"dir:{path}", "warning", path, f"{path} is not writable")
        return EnvCheck(f"dir:{path}", "ok", path, f"{path} exists" + (" and is writable" if writable else ""))

    # ── custom checks ────────────────────────────────────────────────

    def add_check(self, name: str, check_fn: Callable[[], EnvCheck]) -> None:
        """Register a custom check."""
        self._custom_checks.append((name, check_fn))

    def check_all(self) -> list[EnvCheck]:
        """Run built-in + custom checks and return results."""
        results: list[EnvCheck] = []
        results.append(self.check_python_version())
        for _name, fn in self._custom_checks:
            try:
                results.append(fn())
            except Exception as exc:  # noqa: BLE001
                results.append(EnvCheck(_name, "error", None, f"Check raised: {exc}"))
        self._results = list(results)
        return results

    def summary(self) -> str:
        """Return a formatted summary of the last check_all run."""
        results = self._results
        if not results:
            results = self.check_all()
        ok = sum(1 for r in results if r.status == "ok")
        warn = sum(1 for r in results if r.status == "warning")
        err = sum(1 for r in results if r.status == "error")
        lines = [f"Environment: {ok} ok, {warn} warning(s), {err} error(s)"]
        for r in results:
            icon = {"ok": "[ok]", "warning": "[WARN]", "error": "[ERR]"}.get(r.status, "[?]")
            lines.append(f"  {icon} {r.name}: {r.message}")
        return "\n".join(lines)
