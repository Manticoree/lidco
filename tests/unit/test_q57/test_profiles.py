"""Tests for Task 385 — Workspace profiles (ProfileLoader, /profile command, --profile flag)."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestProfileLoader:
    """Tests for ProfileLoader class."""

    def test_builtin_profiles_available(self):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        names = loader.list_profiles()
        assert "frontend" in names
        assert "backend" in names
        assert "data" in names
        assert "devops" in names
        assert "security" in names

    def test_load_builtin_frontend(self):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        data = loader.load("frontend")
        assert data is not None
        assert data["name"] == "frontend"
        assert "description" in data

    def test_load_builtin_backend(self):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        data = loader.load("backend")
        assert data is not None
        assert data["name"] == "backend"
        assert "llm" in data

    def test_load_nonexistent_returns_none(self):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        data = loader.load("nonexistent_profile_xyz")
        assert data is None

    def test_save_and_load_custom_profile(self, tmp_path):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        profile_data = {
            "description": "My custom profile",
            "llm": {"default_model": "gpt-4", "temperature": 0.5},
            "agents": {"default": "architect"},
        }
        loader.save("custom", profile_data, project_dir=tmp_path)
        loaded = loader.load("custom", project_dir=tmp_path)
        assert loaded is not None
        assert loaded["name"] == "custom"
        assert loaded["llm"]["default_model"] == "gpt-4"

    def test_delete_custom_profile(self, tmp_path):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        loader.save("temp-profile", {"description": "temp"}, project_dir=tmp_path)
        deleted = loader.delete("temp-profile", project_dir=tmp_path)
        assert deleted is True
        assert loader.load("temp-profile", project_dir=tmp_path) is None

    def test_delete_nonexistent_returns_false(self, tmp_path):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        result = loader.delete("ghost-profile", project_dir=tmp_path)
        assert result is False

    def test_list_includes_saved_custom_profiles(self, tmp_path):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        loader.save("my-profile", {"description": "custom"}, project_dir=tmp_path)
        names = loader.list_profiles(project_dir=tmp_path)
        assert "my-profile" in names
        assert "frontend" in names  # built-in still present

    def test_project_local_overrides_builtin(self, tmp_path):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        override = {
            "description": "My override of backend",
            "llm": {"default_model": "custom-model", "temperature": 0.9},
        }
        loader.save("backend", override, project_dir=tmp_path)
        loaded = loader.load("backend", project_dir=tmp_path)
        assert loaded is not None
        # Project-local should win for overridden keys
        assert loaded["llm"]["default_model"] == "custom-model"

    def test_load_missing_yaml_gracefully(self, tmp_path):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        # Write a broken yaml
        bad_path = tmp_path / ".lidco" / "profiles"
        bad_path.mkdir(parents=True)
        (bad_path / "broken.yaml").write_text("{{{{invalid yaml", encoding="utf-8")

        # Should not raise, just return None for broken profile
        # (no builtin named "broken")
        result = loader.load("broken", project_dir=tmp_path)
        assert result is None or isinstance(result, dict)

    def test_builtin_security_profile_has_security_agent(self):
        from lidco.core.profiles import ProfileLoader

        loader = ProfileLoader()
        data = loader.load("security")
        assert data is not None
        assert data.get("agents", {}).get("default") == "security"


class TestProfileCLIFlag:
    """Tests for --profile CLI flag."""

    def test_profile_name_in_cliflags(self):
        from lidco.__main__ import CLIFlags
        flags = CLIFlags(profile_name="backend")
        assert flags.profile_name == "backend"

    def test_parse_profile_flag(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags(["--profile", "frontend"])
        assert flags.profile_name == "frontend"

    def test_profile_none_by_default(self):
        from lidco.__main__ import _parse_repl_flags
        flags = _parse_repl_flags([])
        assert flags.profile_name is None
