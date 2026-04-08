"""
Health Check Suite.

Aggregates disk-space, memory, and configuration validity checks into a
single run-all convenience method.
"""
from __future__ import annotations

import datetime
import shutil

_UTC = datetime.timezone.utc


class HealthCheckSuite:
    """Run a set of standardised health checks."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_disk_space(
        self, path: str = ".", min_mb: float = 100.0
    ) -> dict:
        """Check available disk space at *path*.

        Args:
            path: File-system path to check (default current directory).
            min_mb: Minimum acceptable free space in MiB.

        Returns:
            dict with keys:
                "healthy" (bool): True if available_mb >= min_mb
                "available_mb" (float): free space in MiB
                "min_mb" (float): threshold used
                "path" (str): path that was checked
        """
        try:
            usage = shutil.disk_usage(path)
            available_mb = usage.free / (1024 * 1024)
        except Exception:
            available_mb = 0.0
        return {
            "healthy": available_mb >= min_mb,
            "available_mb": available_mb,
            "min_mb": min_mb,
            "path": path,
        }

    def check_memory(self, max_percent: float = 90.0) -> dict:
        """Check current process / system memory usage.

        Uses *psutil* when available; falls back to a best-effort approach
        using ``/proc/meminfo`` (Linux) or reports 0 % used if unavailable.

        Args:
            max_percent: Maximum acceptable used-memory percentage.

        Returns:
            dict with keys:
                "healthy" (bool): True if used_percent <= max_percent
                "used_percent" (float): percentage of memory in use
                "max_percent" (float): threshold used
        """
        used_percent = self._get_memory_percent()
        return {
            "healthy": used_percent <= max_percent,
            "used_percent": used_percent,
            "max_percent": max_percent,
        }

    def check_config_validity(
        self, config: dict, required_keys: list[str]
    ) -> dict:
        """Validate that *config* contains all *required_keys*.

        Args:
            config: The configuration dictionary to validate.
            required_keys: Keys that must be present.

        Returns:
            dict with keys:
                "valid" (bool): True if no required keys are missing
                "missing_keys" (list[str]): required keys absent from config
                "extra_keys" (list[str]): keys present in config but not required
        """
        config_keys = set(config.keys())
        required_set = set(required_keys)
        missing = sorted(required_set - config_keys)
        extra = sorted(config_keys - required_set)
        return {
            "valid": len(missing) == 0,
            "missing_keys": missing,
            "extra_keys": extra,
        }

    def run_all(
        self, path: str = ".", config: dict | None = None
    ) -> dict:
        """Run all health checks and aggregate results.

        Args:
            path: Passed to :meth:`check_disk_space`.
            config: If provided, validated with :meth:`check_config_validity`
                    against a minimal default required-key set.

        Returns:
            dict with keys:
                "overall_healthy" (bool): True if every check reports healthy/valid
                "checks" (dict): mapping of check name → result dict
                "timestamp" (str): ISO-8601 UTC timestamp
        """
        cfg = config if config is not None else {}
        disk = self.check_disk_space(path)
        memory = self.check_memory()
        config_check = self.check_config_validity(cfg, list(cfg.keys()))

        checks = {
            "disk_space": disk,
            "memory": memory,
            "config_validity": config_check,
        }
        overall = all(
            [
                disk["healthy"],
                memory["healthy"],
                config_check["valid"],
            ]
        )
        return {
            "overall_healthy": overall,
            "checks": checks,
            "timestamp": datetime.datetime.now(_UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_memory_percent() -> float:
        """Return used-memory percentage, preferring psutil."""
        try:
            import psutil  # type: ignore[import-not-found]

            return psutil.virtual_memory().percent
        except ImportError:
            pass

        # Fallback: /proc/meminfo (Linux)
        try:
            info: dict[str, int] = {}
            with open("/proc/meminfo", encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) >= 2:
                        info[parts[0].rstrip(":")] = int(parts[1])
            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            if total > 0:
                return round((total - available) / total * 100.0, 1)
        except Exception:
            pass

        return 0.0
