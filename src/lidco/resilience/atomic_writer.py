"""AtomicWriter -- safe file writes via temp+rename, with optional backup (stdlib only)."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class WriteResult:
    """Result of an atomic write operation."""

    path: str
    success: bool
    bytes_written: int
    backup_path: Optional[str] = None


class AtomicWriter:
    """Write files atomically using write-to-temp-then-rename.

    All filesystem operations are performed through injectable callbacks
    so that tests can substitute fakes without touching the real filesystem.
    """

    def __init__(
        self,
        _write_fn: Optional[Callable[..., Any]] = None,
        _rename_fn: Optional[Callable[[str, str], None]] = None,
        _remove_fn: Optional[Callable[[str], None]] = None,
        _exists_fn: Optional[Callable[[str], bool]] = None,
        _read_fn: Optional[Callable[[str], str]] = None,
        _copy_fn: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._write_fn = _write_fn or self._default_write
        self._rename_fn = _rename_fn or os.replace
        self._remove_fn = _remove_fn or os.remove
        self._exists_fn = _exists_fn or os.path.exists
        self._read_fn = _read_fn or self._default_read
        self._copy_fn = _copy_fn or self._default_copy

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, path: str, content: str, encoding: str = "utf-8") -> WriteResult:
        """Atomically write *content* to *path* (temp file then rename)."""
        try:
            encoded = content.encode(encoding)
            tmp_path = path + ".tmp"
            self._write_fn(tmp_path, encoded)
            self._rename_fn(tmp_path, path)
            return WriteResult(path=path, success=True, bytes_written=len(encoded))
        except Exception:
            return WriteResult(path=path, success=False, bytes_written=0)

    def write_json(self, path: str, data: dict) -> WriteResult:
        """Atomically write *data* as pretty-printed JSON to *path*."""
        content = json.dumps(data, indent=2, sort_keys=True)
        return self.write(path, content)

    def write_with_backup(
        self,
        path: str,
        content: str,
        backup_suffix: str = ".bak",
    ) -> WriteResult:
        """Backup existing file (if any) then atomically write *content*."""
        backup_path: Optional[str] = None
        try:
            if self._exists_fn(path):
                backup_path = path + backup_suffix
                self._copy_fn(path, backup_path)
            result = self.write(path, content)
            return WriteResult(
                path=result.path,
                success=result.success,
                bytes_written=result.bytes_written,
                backup_path=backup_path if result.success else None,
            )
        except Exception:
            return WriteResult(path=path, success=False, bytes_written=0)

    def safe_delete(self, path: str, backup: bool = True) -> bool:
        """Delete *path*, optionally creating a backup first. Return success."""
        try:
            if not self._exists_fn(path):
                return False
            if backup:
                backup_path = path + ".bak"
                self._copy_fn(path, backup_path)
            self._remove_fn(path)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Default I/O implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _default_write(path: str, data: bytes) -> None:
        with open(path, "wb") as fh:
            fh.write(data)

    @staticmethod
    def _default_read(path: str) -> str:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def _default_copy(src: str, dst: str) -> None:
        with open(src, "rb") as f_in:
            content = f_in.read()
        with open(dst, "wb") as f_out:
            f_out.write(content)
