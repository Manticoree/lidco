"""Tests for SetupWizard and detect_project_type — Q64 Task 435."""

from __future__ import annotations

import pytest
from pathlib import Path


class TestDetectProjectType:
    def test_detects_python_from_pyproject(self, tmp_path):
        from lidco.cli.wizard import detect_project_type
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        assert detect_project_type(tmp_path) == "python"

    def test_detects_python_from_requirements(self, tmp_path):
        from lidco.cli.wizard import detect_project_type
        (tmp_path / "requirements.txt").write_text("requests")
        assert detect_project_type(tmp_path) == "python"

    def test_detects_javascript(self, tmp_path):
        from lidco.cli.wizard import detect_project_type
        (tmp_path / "package.json").write_text("{}")
        assert detect_project_type(tmp_path) == "javascript"

    def test_detects_go(self, tmp_path):
        from lidco.cli.wizard import detect_project_type
        (tmp_path / "go.mod").write_text("module example")
        assert detect_project_type(tmp_path) == "go"

    def test_detects_rust(self, tmp_path):
        from lidco.cli.wizard import detect_project_type
        (tmp_path / "Cargo.toml").write_text("[package]")
        assert detect_project_type(tmp_path) == "rust"

    def test_returns_unknown_for_empty_dir(self, tmp_path):
        from lidco.cli.wizard import detect_project_type
        assert detect_project_type(tmp_path) == "unknown"


class TestWizardResult:
    def test_fields(self):
        from lidco.cli.wizard import WizardResult
        result = WizardResult(
            project_type="python",
            agent="coder",
            model="anthropic/claude-sonnet-4-5",
            api_key_set=False,
        )
        assert result.project_type == "python"
        assert result.api_key_set is False


class TestSetupWizard:
    def test_detect_method(self, tmp_path):
        from lidco.cli.wizard import SetupWizard
        (tmp_path / "pyproject.toml").write_text("[project]")
        wizard = SetupWizard(project_dir=tmp_path)
        assert wizard._project_dir == tmp_path

    def test_generate_config_writes_file(self, tmp_path):
        from lidco.cli.wizard import SetupWizard, WizardResult
        wizard = SetupWizard(project_dir=tmp_path)
        result = WizardResult(
            project_type="python",
            agent="coder",
            model="anthropic/claude-sonnet-4-5",
            api_key_set=False,
        )
        config_path = wizard.generate_config(result)
        assert config_path.exists()
        content = config_path.read_text()
        assert "coder" in content
        assert "python" in content

    def test_generate_config_custom_path(self, tmp_path):
        from lidco.cli.wizard import SetupWizard, WizardResult
        wizard = SetupWizard(project_dir=tmp_path)
        result = WizardResult(project_type="go", agent="architect", model="gpt-4o", api_key_set=True)
        dest = tmp_path / "custom_config.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        config_path = wizard.generate_config(result, output_path=dest)
        assert config_path == dest
        assert dest.exists()

    @pytest.mark.asyncio
    async def test_run_falls_back_to_defaults(self, tmp_path):
        """run() should fall back gracefully when no TTY / prompt_toolkit absent."""
        from lidco.cli.wizard import SetupWizard
        from unittest.mock import patch
        wizard = SetupWizard(project_dir=tmp_path)
        # Force interactive path to fail (EOFError simulates non-interactive)
        with patch.object(wizard, "_run_interactive", side_effect=EOFError):
            result = await wizard.run()
        assert result.agent == "coder"
