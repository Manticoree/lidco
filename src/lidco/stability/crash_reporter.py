"""
Crash Reporter.

Captures exception context, formats human-readable reports, persists them
to disk, and provides reproducibility information.
"""
from __future__ import annotations

import datetime
import json
import os
import platform
import sys
import traceback

_UTC = datetime.timezone.utc


# Environment variable prefixes considered safe to include in reports.
_SAFE_ENV_PREFIXES: tuple[str, ...] = (
    "PATH",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "CONDA_",
    "LANG",
    "LC_",
    "TERM",
    "SHELL",
    "HOME",
    "USER",
    "USERNAME",
    "LOGNAME",
    "PWD",
    "TMPDIR",
    "TEMP",
    "TMP",
    "XDG_",
)


class CrashReporter:
    """Capture, format, and persist crash information."""

    def __init__(self, report_dir: str = ".lidco/crashes") -> None:
        self._report_dir = report_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture_context(self, exception: Exception) -> dict:
        """Capture context surrounding *exception*.

        Args:
            exception: The caught exception instance.

        Returns:
            dict with keys:
                "exception_type" (str): class name of the exception
                "message" (str): str(exception)
                "traceback" (str): formatted traceback text
                "timestamp" (str): ISO-8601 UTC timestamp
                "python_version" (str): sys.version
                "platform" (str): platform.platform() string
        """
        tb_text = "".join(
            traceback.format_exception(type(exception), exception, exception.__traceback__)
        )
        return {
            "exception_type": type(exception).__name__,
            "message": str(exception),
            "traceback": tb_text,
            "timestamp": datetime.datetime.now(_UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "python_version": sys.version,
            "platform": platform.platform(),
        }

    def format_report(self, context: dict) -> str:
        """Format *context* (as returned by :meth:`capture_context`) into a
        human-readable crash report.

        Args:
            context: Crash context dict.

        Returns:
            Multi-line string report.
        """
        lines: list[str] = [
            "=" * 60,
            "CRASH REPORT",
            "=" * 60,
            f"Timestamp      : {context.get('timestamp', 'unknown')}",
            f"Exception type : {context.get('exception_type', 'unknown')}",
            f"Message        : {context.get('message', '')}",
            f"Python version : {context.get('python_version', 'unknown')}",
            f"Platform       : {context.get('platform', 'unknown')}",
            "",
            "Traceback:",
            "-" * 40,
            context.get("traceback", "(no traceback)").rstrip(),
            "=" * 60,
        ]
        return "\n".join(lines)

    def save_report(self, context: dict, path: str | None = None) -> dict:
        """Save *context* as a JSON crash report.

        If *path* is None, a timestamped file is created inside
        :attr:`_report_dir`.

        Args:
            context: Crash context dict to persist.
            path: Explicit file path; auto-generated when omitted.

        Returns:
            dict with keys:
                "saved" (bool): True if write succeeded
                "path" (str): resolved file path
                "size_bytes" (int): bytes written (0 on failure)
        """
        if path is None:
            ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            exc_type = context.get("exception_type", "crash")
            filename = f"crash_{exc_type}_{ts}.json"
            path = os.path.join(self._report_dir, filename)

        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            payload = json.dumps(context, indent=2, default=str)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(payload)
            return {
                "saved": True,
                "path": path,
                "size_bytes": len(payload.encode("utf-8")),
            }
        except Exception:  # noqa: BLE001
            return {"saved": False, "path": path, "size_bytes": 0}

    def get_reproducibility_info(self) -> dict:
        """Collect system information useful for reproducing a crash.

        Returns:
            dict with keys:
                "python_version" (str): sys.version
                "platform" (str): platform.platform() string
                "cwd" (str): current working directory
                "env_vars" (dict[str, str]): filtered safe subset of os.environ
        """
        env_vars: dict[str, str] = {}
        for key, value in os.environ.items():
            if any(key.upper().startswith(prefix.upper()) for prefix in _SAFE_ENV_PREFIXES):
                env_vars[key] = value

        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "cwd": os.getcwd(),
            "env_vars": env_vars,
        }
