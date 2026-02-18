"""Shared test fixtures for LIDCO."""

import pytest


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with basic structure."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')\n")
    (tmp_path / "README.md").write_text("# Test Project\n")
    return tmp_path
