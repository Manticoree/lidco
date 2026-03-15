"""Tests for Task 400 — VenvManager (src/lidco/tools/venv_manager.py)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.tools.venv_manager import VenvInfo, VenvManager


# ── VenvInfo ─────────────────────────────────────────────────────────────────

class TestVenvInfo:
    def test_fields(self):
        p = Path("/tmp/venvs/myenv")
        info = VenvInfo(name="myenv", path=p, python_version="3.11.5", size_mb=15.3)
        assert info.name == "myenv"
        assert info.path == p
        assert info.python_version == "3.11.5"
        assert info.size_mb == 15.3

    def test_frozen(self):
        info = VenvInfo(name="x", path=Path("/x"), python_version="3.11", size_mb=0.0)
        with pytest.raises((AttributeError, TypeError)):
            info.name = "y"  # type: ignore[misc]


# ── VenvManager.create ────────────────────────────────────────────────────────

class TestVenvManagerCreate:
    def test_create_calls_venv(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            mgr = VenvManager()
            # Mock the size calculation to avoid filesystem ops on non-existent venv
            with patch.object(mgr, "_get_python_version", return_value="3.11.0"), \
                 patch.object(mgr, "_calc_size_mb", return_value=5.0):
                info = mgr.create("myenv", tmp_path)
        assert info.name == "myenv"
        assert info.python_version == "3.11.0"
        assert info.size_mb == 5.0
        mock_run.assert_called_once()

    def test_create_propagates_error(self, tmp_path):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "venv")):
            mgr = VenvManager()
            with pytest.raises(subprocess.CalledProcessError):
                mgr.create("bad_env", tmp_path)


# ── VenvManager.list_venvs ────────────────────────────────────────────────────

class TestVenvManagerList:
    def test_empty_dir(self, tmp_path):
        mgr = VenvManager()
        result = mgr.list_venvs(tmp_path)
        assert result == []

    def test_nonexistent_dir(self, tmp_path):
        mgr = VenvManager()
        result = mgr.list_venvs(tmp_path / "does_not_exist")
        assert result == []

    def test_lists_venvs_with_pyvenv_cfg(self, tmp_path):
        # Create a fake venv structure
        venv_dir = tmp_path / "testenv"
        venv_dir.mkdir()
        cfg = venv_dir / "pyvenv.cfg"
        cfg.write_text("version = 3.11.0\nhome = /usr/bin\n")
        (venv_dir / "bin").mkdir()

        mgr = VenvManager()
        result = mgr.list_venvs(tmp_path)
        assert len(result) == 1
        assert result[0].name == "testenv"
        assert result[0].python_version == "3.11.0"

    def test_ignores_non_venv_dirs(self, tmp_path):
        # Directory without pyvenv.cfg
        (tmp_path / "notavenv").mkdir()
        mgr = VenvManager()
        result = mgr.list_venvs(tmp_path)
        assert result == []


# ── VenvManager.delete ────────────────────────────────────────────────────────

class TestVenvManagerDelete:
    def test_delete_existing(self, tmp_path):
        venv_dir = tmp_path / "myenv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("version = 3.11\n")

        mgr = VenvManager()
        assert mgr.delete("myenv", tmp_path) is True
        assert not venv_dir.exists()

    def test_delete_nonexistent(self, tmp_path):
        mgr = VenvManager()
        assert mgr.delete("ghost_env", tmp_path) is False


# ── VenvManager.get_activate_path ────────────────────────────────────────────

class TestGetActivatePath:
    def test_unix_path_preferred(self, tmp_path):
        venv_dir = tmp_path / "myenv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        activate = bin_dir / "activate"
        activate.write_text("# activate script")
        info = VenvInfo(name="myenv", path=venv_dir, python_version="3.11", size_mb=0.0)
        mgr = VenvManager()
        path = mgr.get_activate_path(info)
        assert str(activate) == path

    def test_windows_fallback(self, tmp_path):
        venv_dir = tmp_path / "myenv"
        venv_dir.mkdir()
        info = VenvInfo(name="myenv", path=venv_dir, python_version="3.11", size_mb=0.0)
        mgr = VenvManager()
        path = mgr.get_activate_path(info)
        # Should return the Scripts/activate path even if it doesn't exist
        assert "Scripts" in path or "bin" in path


# ── get_python_version helper ────────────────────────────────────────────────

class TestGetPythonVersion:
    def test_reads_version_from_cfg(self, tmp_path):
        venv_dir = tmp_path / "myenv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin\nversion = 3.12.1\n")
        mgr = VenvManager()
        assert mgr._get_python_version(venv_dir) == "3.12.1"

    def test_missing_cfg_returns_unknown(self, tmp_path):
        venv_dir = tmp_path / "myenv"
        venv_dir.mkdir()
        mgr = VenvManager()
        assert mgr._get_python_version(venv_dir) == "unknown"
