"""Virtual environment manager — create, list, and delete project venvs."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VenvInfo:
    """Information about a virtual environment."""

    name: str
    path: Path
    python_version: str
    size_mb: float


class VenvManager:
    """Manage Python virtual environments under a base directory."""

    def create(self, name: str, base_dir: Path) -> VenvInfo:
        """Create a new venv named *name* under *base_dir*."""
        venv_path = base_dir / name
        venv_path.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            check=True,
            capture_output=True,
            text=True,
        )

        python_version = self._get_python_version(venv_path)
        size_mb = self._calc_size_mb(venv_path)
        return VenvInfo(name=name, path=venv_path, python_version=python_version, size_mb=size_mb)

    def list_venvs(self, base_dir: Path) -> list[VenvInfo]:
        """Return all venvs found directly under *base_dir*."""
        if not base_dir.exists():
            return []
        result: list[VenvInfo] = []
        for candidate in sorted(base_dir.iterdir()):
            if not candidate.is_dir():
                continue
            # A venv has a pyvenv.cfg marker
            if not (candidate / "pyvenv.cfg").exists():
                continue
            python_version = self._get_python_version(candidate)
            size_mb = self._calc_size_mb(candidate)
            result.append(
                VenvInfo(
                    name=candidate.name,
                    path=candidate,
                    python_version=python_version,
                    size_mb=size_mb,
                )
            )
        return result

    def delete(self, name: str, base_dir: Path) -> bool:
        """Delete venv *name* from *base_dir*. Returns True if found and deleted."""
        import shutil
        venv_path = base_dir / name
        if not venv_path.exists():
            return False
        shutil.rmtree(venv_path)
        return True

    def get_activate_path(self, venv_info: VenvInfo) -> str:
        """Return the activation script path for the given venv."""
        # Unix
        unix_path = venv_info.path / "bin" / "activate"
        if unix_path.exists():
            return str(unix_path)
        # Windows
        win_path = venv_info.path / "Scripts" / "activate"
        return str(win_path)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_python_version(self, venv_path: Path) -> str:
        """Determine the Python version inside the venv via pyvenv.cfg."""
        cfg = venv_path / "pyvenv.cfg"
        if cfg.exists():
            for line in cfg.read_text().splitlines():
                if line.startswith("version"):
                    return line.split("=", 1)[1].strip()
        return "unknown"

    def _calc_size_mb(self, path: Path) -> float:
        """Return the total size of *path* in megabytes."""
        total = 0
        try:
            for f in path.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        except (OSError, PermissionError):
            pass
        return round(total / (1024 * 1024), 2)
