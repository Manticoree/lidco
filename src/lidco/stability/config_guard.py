"""
Config Corruption Guard.

Provides atomic file writes, corruption detection, backup-before-write,
and recovery from backup for configuration files.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time


class ConfigCorruptionGuard:
    """Guards config files against corruption with atomic writes and backups."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_corruption(self, content: str, format: str = "json") -> dict:
        """Check if content is valid JSON or YAML.

        Args:
            content: The string content to validate.
            format: "json" or "yaml".

        Returns:
            dict with keys:
                "valid" (bool): True if content parses without error
                "error" (str or None): parse error message if invalid
                "format" (str): the format that was checked
                "recoverable" (bool): True if partial recovery is possible
        """
        fmt = format.lower().strip()

        if fmt == "json":
            return self._detect_json(content, fmt)
        elif fmt in ("yaml", "yml"):
            return self._detect_yaml(content, fmt)
        else:
            return {
                "valid": False,
                "error": f"Unsupported format: {format!r}",
                "format": fmt,
                "recoverable": False,
            }

    def atomic_write(self, path: str, content: str) -> dict:
        """Write content to path atomically via a temp file + rename.

        Args:
            path: Destination file path.
            content: String content to write.

        Returns:
            dict with keys:
                "success" (bool): True if write succeeded
                "path" (str): destination path
                "backup_path" (str or None): backup path if a backup was made
        """
        backup_path: str | None = None

        try:
            dir_path = os.path.dirname(os.path.abspath(path)) or "."
            os.makedirs(dir_path, exist_ok=True)

            # Backup existing file
            if os.path.exists(path):
                backup_result = self.backup_before_write(path)
                if backup_result["backed_up"]:
                    backup_path = backup_result["backup_path"]

            # Write to temp file in the same directory (ensures same filesystem)
            fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(content)
                # Atomic rename
                shutil.move(tmp_path, path)
            except Exception:
                # Clean up temp if rename fails
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            return {"success": True, "path": path, "backup_path": backup_path}

        except Exception as exc:
            return {"success": False, "path": path, "backup_path": backup_path}

    def backup_before_write(self, path: str) -> dict:
        """Create a timestamped backup of an existing file.

        Args:
            path: Path to the file to back up.

        Returns:
            dict with keys:
                "backed_up" (bool): True if backup was created
                "backup_path" (str): path of the backup file (empty string if not backed up)
                "original_size" (int): size in bytes of the original file
        """
        if not os.path.exists(path):
            return {"backed_up": False, "backup_path": "", "original_size": 0}

        try:
            original_size = os.path.getsize(path)
            timestamp = int(time.time() * 1000)
            backup_path = f"{path}.{timestamp}.bak"
            shutil.copy2(path, backup_path)
            return {
                "backed_up": True,
                "backup_path": backup_path,
                "original_size": original_size,
            }
        except OSError:
            return {"backed_up": False, "backup_path": "", "original_size": 0}

    def recover(self, path: str, backup_path: str) -> dict:
        """Recover a file from its backup.

        Args:
            path: Destination path to restore to.
            backup_path: Path of the backup file.

        Returns:
            dict with keys:
                "recovered" (bool): True if recovery succeeded
                "path" (str): destination path
                "source" (str): backup source path that was used
        """
        if not os.path.exists(backup_path):
            return {"recovered": False, "path": path, "source": backup_path}

        try:
            dir_path = os.path.dirname(os.path.abspath(path)) or "."
            os.makedirs(dir_path, exist_ok=True)
            shutil.copy2(backup_path, path)
            return {"recovered": True, "path": path, "source": backup_path}
        except OSError:
            return {"recovered": False, "path": path, "source": backup_path}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_json(self, content: str, fmt: str) -> dict:
        try:
            json.loads(content)
            return {"valid": True, "error": None, "format": fmt, "recoverable": False}
        except json.JSONDecodeError as exc:
            # Assess recoverability: if we can parse up to the error position
            recoverable = exc.pos > 0 and exc.pos < len(content)
            return {
                "valid": False,
                "error": str(exc),
                "format": fmt,
                "recoverable": recoverable,
            }

    def _detect_yaml(self, content: str, fmt: str) -> dict:
        try:
            import yaml  # type: ignore[import]
            yaml.safe_load(content)
            return {"valid": True, "error": None, "format": fmt, "recoverable": False}
        except ImportError:
            # No yaml library — fall back to basic heuristic
            stripped = content.strip()
            valid = len(stripped) == 0 or not stripped.startswith("{")
            return {
                "valid": valid,
                "error": None if valid else "Cannot parse YAML: library unavailable",
                "format": fmt,
                "recoverable": False,
            }
        except Exception as exc:
            return {
                "valid": False,
                "error": str(exc),
                "format": fmt,
                "recoverable": True,
            }
