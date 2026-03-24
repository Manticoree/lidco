"""Tests for Task 462: /spec slash command."""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lidco.spec.writer import SpecDocument, SpecWriter
from lidco.spec.task_decomposer import SpecTask, TaskDecomposer
from lidco.cli.commands.spec_cmds import (
    _spec_new,
    _spec_show,
    _spec_tasks,
    _spec_done,
    _spec_check,
    _spec_reset,
    _spec_help,
)


def _write_full_spec(project_dir: Path) -> None:
    """Set up a complete spec in project_dir."""
    spec_dir = project_dir / ".lidco" / "spec"
    spec_dir.mkdir(parents=True, exist_ok=True)
    doc = SpecDocument(
        title="Test Feature",
        overview="A test feature.",
        user_stories=["As a user I want test so that pass"],
        acceptance_criteria=["The system shall test when invoked"],
        out_of_scope=["None"],
    )
    SpecWriter()._save(doc, project_dir)

    td = TaskDecomposer()
    from lidco.spec.design_doc import Component, DesignDocument
    design = DesignDocument(
        components=[Component("Tester", "Tests things", "src/tester.py")],
    )
    td.decompose(design, project_dir)


class TestSpecNew:
    def test_spec_new_no_description(self, tmp_path):
        result = asyncio.run(_spec_new("", tmp_path))
        assert "Usage" in result

    def test_spec_new_creates_files(self, tmp_path):
        result = asyncio.run(_spec_new("Build a cache system", tmp_path))
        assert (tmp_path / ".lidco" / "spec" / "requirements.md").exists()
        assert (tmp_path / ".lidco" / "spec" / "design.md").exists()
        assert (tmp_path / ".lidco" / "spec" / "tasks.md").exists()

    def test_spec_new_returns_summary(self, tmp_path):
        result = asyncio.run(_spec_new("Notification service", tmp_path))
        assert "tasks generated" in result.lower() or "Task" in result

    def test_spec_new_shows_task_ids(self, tmp_path):
        result = asyncio.run(_spec_new("Auth module", tmp_path))
        assert "T1" in result


class TestSpecShow:
    def test_show_no_spec_returns_hint(self, tmp_path):
        result = _spec_show(tmp_path)
        assert "No spec found" in result

    def test_show_with_spec(self, tmp_path):
        _write_full_spec(tmp_path)
        result = _spec_show(tmp_path)
        assert "Test Feature" in result

    def test_show_includes_acceptance_criteria(self, tmp_path):
        _write_full_spec(tmp_path)
        result = _spec_show(tmp_path)
        assert "The system shall" in result

    def test_show_includes_task_summary(self, tmp_path):
        _write_full_spec(tmp_path)
        result = _spec_show(tmp_path)
        assert "Tasks" in result or "T1" in result


class TestSpecTasks:
    def test_tasks_no_spec_returns_hint(self, tmp_path):
        result = _spec_tasks(tmp_path)
        assert "No tasks" in result

    def test_tasks_with_spec(self, tmp_path):
        _write_full_spec(tmp_path)
        result = _spec_tasks(tmp_path)
        assert "T1" in result

    def test_tasks_shows_checkboxes(self, tmp_path):
        _write_full_spec(tmp_path)
        result = _spec_tasks(tmp_path)
        assert "[ ]" in result or "[x]" in result


class TestSpecDone:
    def test_done_marks_task(self, tmp_path):
        _write_full_spec(tmp_path)
        result = _spec_done("T1", tmp_path)
        assert "T1" in result and "done" in result.lower()

    def test_done_nonexistent_task(self, tmp_path):
        _write_full_spec(tmp_path)
        result = _spec_done("T999", tmp_path)
        assert "not found" in result.lower()


class TestSpecCheck:
    def test_check_no_spec(self, tmp_path):
        result = _spec_check(tmp_path)
        assert "Drift" in result or "spec" in result.lower()

    def test_check_with_spec(self, tmp_path):
        _write_full_spec(tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", returncode=0)
            result = _spec_check(tmp_path)
        assert "Drift" in result or "Confidence" in result


class TestSpecReset:
    def test_reset_without_confirm(self, tmp_path):
        result = _spec_reset(tmp_path, confirmed=False)
        assert "--yes" in result

    def test_reset_with_confirm_deletes_files(self, tmp_path):
        _write_full_spec(tmp_path)
        result = _spec_reset(tmp_path, confirmed=True)
        assert "requirements.md" in result
        assert not (tmp_path / ".lidco" / "spec" / "requirements.md").exists()

    def test_reset_no_files(self, tmp_path):
        result = _spec_reset(tmp_path, confirmed=True)
        assert "No spec files" in result


class TestSpecHelp:
    def test_help_contains_subcommands(self):
        h = _spec_help()
        assert "/spec new" in h
        assert "/spec show" in h
        assert "/spec tasks" in h
        assert "/spec done" in h
        assert "/spec check" in h
        assert "/spec reset" in h
