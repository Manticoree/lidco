"""Tests for T597 PlaybookEngine."""
import asyncio
import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lidco.playbooks.engine import (
    Playbook,
    PlaybookEngine,
    PlaybookResult,
    PlaybookStep,
    _parse_step,
)


def _evaluate_condition(condition: str, ctx: dict) -> bool:
    """Thin wrapper so tests can call the instance method as a function."""
    engine = PlaybookEngine()
    return engine._evaluate_condition(condition, ctx)


# ---------------------------------------------------------------------------
# _parse_step
# ---------------------------------------------------------------------------

class TestParseStep:
    def test_run_step(self):
        step = _parse_step({"type": "run", "command": "echo hello"})
        assert step.type == "run"
        assert step.command == "echo hello"

    def test_prompt_step(self):
        step = _parse_step({"type": "prompt", "message": "Explain {{output}}"})
        assert step.type == "prompt"
        assert "{{output}}" in step.message

    def test_tool_step(self):
        step = _parse_step({"type": "tool", "command": "/git status"})
        assert step.type == "tool"
        assert step.command == "/git status"

    def test_condition_step(self):
        raw = {
            "type": "condition",
            "if": "{{exit_code}} == 0",
            "then": [{"type": "run", "command": "echo ok"}],
            "else": [{"type": "run", "command": "echo fail"}],
        }
        step = _parse_step(raw)
        assert step.type == "condition"
        assert step.condition == "{{exit_code}} == 0"
        assert len(step.then_steps) == 1
        assert len(step.else_steps) == 1

    def test_missing_type_defaults_run(self):
        step = _parse_step({"command": "ls"})
        assert step.type == "run"


# ---------------------------------------------------------------------------
# _evaluate_condition
# ---------------------------------------------------------------------------

class TestEvaluateCondition:
    def test_true_literals(self):
        assert _evaluate_condition("true", {}) is True
        assert _evaluate_condition("yes", {}) is True
        assert _evaluate_condition("1", {}) is True

    def test_false_literals(self):
        assert _evaluate_condition("false", {}) is False
        assert _evaluate_condition("no", {}) is False
        assert _evaluate_condition("0", {}) is False
        assert _evaluate_condition("", {}) is False

    def test_equality(self):
        assert _evaluate_condition("0 == 0", {}) is True
        assert _evaluate_condition("0 == 1", {}) is False

    def test_inequality(self):
        assert _evaluate_condition("x != y", {}) is True
        assert _evaluate_condition("x != x", {}) is False

    def test_non_empty_string_truthy(self):
        assert _evaluate_condition("some_text", {}) is True


# ---------------------------------------------------------------------------
# PlaybookEngine — list / load (no yaml available → graceful)
# ---------------------------------------------------------------------------

class TestPlaybookEngineNoYaml:
    """When yaml is not installed, load() raises ImportError."""

    def test_load_raises_import_error_when_no_yaml(self, tmp_path):
        pb_dir = tmp_path / ".lidco" / "playbooks"
        pb_dir.mkdir(parents=True)
        (pb_dir / "test.yaml").write_text("name: test\nsteps: []\n")

        import lidco.playbooks.engine as engine_mod
        original = engine_mod.yaml

        try:
            engine_mod.yaml = None  # type: ignore[assignment]
            engine = PlaybookEngine(project_root=str(tmp_path))
            with pytest.raises(ImportError):
                engine.load("test")
        finally:
            engine_mod.yaml = original

    def test_list_returns_empty_when_no_yaml(self, tmp_path):
        pb_dir = tmp_path / ".lidco" / "playbooks"
        pb_dir.mkdir(parents=True)
        (pb_dir / "test.yaml").write_text("name: test\nsteps: []\n")

        import lidco.playbooks.engine as engine_mod
        original = engine_mod.yaml

        try:
            engine_mod.yaml = None  # type: ignore[assignment]
            engine = PlaybookEngine(project_root=str(tmp_path))
            result = engine.list()
            assert result == []
        finally:
            engine_mod.yaml = original


# ---------------------------------------------------------------------------
# PlaybookEngine — with yaml mock
# ---------------------------------------------------------------------------

SAMPLE_YAML_DATA = {
    "name": "deploy",
    "description": "Deploy to production",
    "steps": [
        {"type": "run", "command": "echo building"},
        {"type": "run", "command": "echo deploying"},
    ],
}


def _make_engine_with_yaml(tmp_path, yaml_data=None):
    """Create engine with mocked yaml that returns *yaml_data*."""
    pb_dir = tmp_path / ".lidco" / "playbooks"
    pb_dir.mkdir(parents=True)
    (pb_dir / "deploy.yaml").write_text("placeholder")

    import lidco.playbooks.engine as engine_mod
    original_yaml = engine_mod.yaml

    fake_yaml = MagicMock()
    fake_yaml.safe_load.return_value = yaml_data or SAMPLE_YAML_DATA
    engine_mod.yaml = fake_yaml

    engine = PlaybookEngine(project_root=str(tmp_path))
    return engine, engine_mod, original_yaml


class TestPlaybookEngineWithYaml:
    def test_list_returns_playbooks(self, tmp_path):
        engine, mod, orig = _make_engine_with_yaml(tmp_path)
        try:
            books = engine.list()
            assert len(books) == 1
            assert books[0].name == "deploy"
        finally:
            mod.yaml = orig

    def test_load_returns_playbook(self, tmp_path):
        engine, mod, orig = _make_engine_with_yaml(tmp_path)
        try:
            book = engine.load("deploy")
            assert book.name == "deploy"
            assert book.description == "Deploy to production"
            assert len(book.steps) == 2
        finally:
            mod.yaml = orig

    def test_load_unknown_raises_key_error(self, tmp_path):
        engine, mod, orig = _make_engine_with_yaml(tmp_path)
        try:
            with pytest.raises(KeyError, match="not found"):
                engine.load("unknown")
        finally:
            mod.yaml = orig

    def test_project_overrides_global(self, tmp_path):
        global_dir = tmp_path / "home" / ".lidco" / "playbooks"
        global_dir.mkdir(parents=True)
        (global_dir / "deploy.yaml").write_text("placeholder-global")

        project_dir = tmp_path / "proj" / ".lidco" / "playbooks"
        project_dir.mkdir(parents=True)
        (project_dir / "deploy.yaml").write_text("placeholder-project")

        import lidco.playbooks.engine as engine_mod
        original_yaml = engine_mod.yaml

        call_count = {"n": 0}
        data_by_call = [
            {"name": "deploy-global", "description": "global", "steps": []},
            {"name": "deploy-project", "description": "project", "steps": []},
        ]

        fake_yaml = MagicMock()
        def side_effect(fh):
            n = call_count["n"]
            call_count["n"] += 1
            return data_by_call[n % 2]
        fake_yaml.safe_load.side_effect = side_effect

        engine_mod.yaml = fake_yaml
        try:
            engine = PlaybookEngine(
                project_root=str(tmp_path / "proj"),
                global_root=str(tmp_path / "home"),
            )
            # The discover order is global first, project second → project wins
            paths = engine._discover_paths()
            assert "deploy" in paths
        finally:
            engine_mod.yaml = original_yaml


# ---------------------------------------------------------------------------
# Execution — run steps with mocked subprocess
# ---------------------------------------------------------------------------

class TestPlaybookExecution:
    def test_execute_run_step_success(self, tmp_path):
        engine, mod, orig = _make_engine_with_yaml(tmp_path)
        try:
            book = engine.load("deploy")
        finally:
            mod.yaml = orig

        with patch("lidco.playbooks.engine.subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "built\n"
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc

            result = engine.execute_playbook(book)

        assert result.success is True
        assert result.steps_completed == 2
        assert result.steps_total == 2

    def test_execute_run_step_failure_stops_pipeline(self, tmp_path):
        engine, mod, orig = _make_engine_with_yaml(tmp_path)
        try:
            book = engine.load("deploy")
        finally:
            mod.yaml = orig

        with patch("lidco.playbooks.engine.subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stdout = ""
            mock_proc.stderr = "error"
            mock_run.return_value = mock_proc

            result = engine.execute_playbook(book)

        assert result.success is False
        assert result.steps_completed == 0

    def test_execute_prompt_step_no_callback(self, tmp_path):
        data = {
            "name": "test",
            "description": "",
            "steps": [{"type": "prompt", "message": "Say hello"}],
        }
        engine, mod, orig = _make_engine_with_yaml(tmp_path, yaml_data=data)
        try:
            book = engine.load("deploy")
        finally:
            mod.yaml = orig

        result = engine.execute_playbook(book)
        assert result.success is False
        assert "callback" in result.step_results[0].error

    def test_execute_prompt_step_with_callback(self, tmp_path):
        data = {
            "name": "test",
            "description": "",
            "steps": [{"type": "prompt", "message": "Say {{name}}"}],
        }
        engine, mod, orig = _make_engine_with_yaml(tmp_path, yaml_data=data)
        try:
            book = engine.load("deploy")
        finally:
            mod.yaml = orig

        engine._llm_callback = lambda msg: f"Hello {msg}"
        result = engine.execute_playbook(book, variables={"name": "world"})

        assert result.success is True
        assert "Say world" in result.output

    def test_execute_tool_step_with_callback(self, tmp_path):
        data = {
            "name": "test",
            "description": "",
            "steps": [{"type": "tool", "command": "/git status"}],
        }
        engine, mod, orig = _make_engine_with_yaml(tmp_path, yaml_data=data)
        try:
            book = engine.load("deploy")
        finally:
            mod.yaml = orig

        engine._tool_callback = lambda cmd: f"tool: {cmd}"
        result = engine.execute_playbook(book)

        assert result.success is True
        assert "/git status" in result.output

    def test_execute_condition_step_true_branch(self, tmp_path):
        data = {
            "name": "test",
            "description": "",
            "steps": [
                {
                    "type": "condition",
                    "if": "{{flag}} == yes",
                    "then": [{"type": "run", "command": "echo YES"}],
                    "else": [{"type": "run", "command": "echo NO"}],
                }
            ],
        }
        engine, mod, orig = _make_engine_with_yaml(tmp_path, yaml_data=data)
        try:
            book = engine.load("deploy")
        finally:
            mod.yaml = orig

        with patch("lidco.playbooks.engine.subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "YES\n"
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc

            result = engine.execute_playbook(book, variables={"flag": "yes"})

        assert result.success is True
        assert "YES" in result.output

    def test_execute_unknown_step_type_fails(self, tmp_path):
        engine, mod, orig = _make_engine_with_yaml(tmp_path)
        try:
            book = engine.load("deploy")
        finally:
            mod.yaml = orig

        # Manually inject an unknown step
        book.steps = [PlaybookStep(type="unknown")]
        result = engine.execute_playbook(book)
        assert result.success is False

    def test_variable_interpolation(self, tmp_path):
        data = {
            "name": "test",
            "description": "",
            "steps": [{"type": "run", "command": "echo {{greeting}}"}],
        }
        engine, mod, orig = _make_engine_with_yaml(tmp_path, yaml_data=data)
        try:
            book = engine.load("deploy")
        finally:
            mod.yaml = orig

        with patch("lidco.playbooks.engine.subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "hi\n"
            mock_proc.stderr = ""
            mock_run.return_value = mock_proc

            engine.execute_playbook(book, variables={"greeting": "hi"})
            called_cmd = mock_run.call_args[0][0]
            assert "hi" in called_cmd

    def test_output_propagated_as_context(self, tmp_path):
        data = {
            "name": "chain",
            "description": "",
            "steps": [
                {"type": "run", "command": "echo step1"},
                {"type": "run", "command": "echo {{output}}"},
            ],
        }
        engine, mod, orig = _make_engine_with_yaml(tmp_path, yaml_data=data)
        try:
            book = engine.load("deploy")
        finally:
            mod.yaml = orig

        call_n = {"n": 0}
        def side_effect(*a, **kw):
            n = call_n["n"]
            call_n["n"] += 1
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stdout = "step1_output\n" if n == 0 else "used_output\n"
            mock_proc.stderr = ""
            return mock_proc

        with patch("lidco.playbooks.engine.subprocess.run", side_effect=side_effect):
            result = engine.execute_playbook(book)

        assert result.success is True


# ---------------------------------------------------------------------------
# PlaybookResult
# ---------------------------------------------------------------------------

class TestPlaybookResult:
    def test_output_joins_non_empty(self):
        from lidco.playbooks.engine import StepResult
        result = PlaybookResult(
            name="x",
            steps_completed=2,
            steps_total=2,
            success=True,
            step_results=[
                StepResult(0, "run", True, output="line1"),
                StepResult(1, "run", True, output=""),
                StepResult(2, "run", True, output="line2"),
            ],
        )
        assert result.output == "line1\nline2"
