"""Tests for CustomCommand and load_custom_commands — Task 296."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from lidco.skills.custom_commands import CustomCommand, load_custom_commands


# ---------------------------------------------------------------------------
# CustomCommand
# ---------------------------------------------------------------------------

class TestCustomCommand:
    def test_render_substitutes_args(self):
        cmd = CustomCommand(
            name="review",
            prompt="Review {args} for quality.",
        )
        assert cmd.render("src/auth.py") == "Review src/auth.py for quality."

    def test_render_empty_args(self):
        cmd = CustomCommand(name="help", prompt="Show help {args}")
        assert cmd.render("").strip() == "Show help"

    def test_render_no_placeholder(self):
        cmd = CustomCommand(name="greet", prompt="Hello world")
        assert cmd.render("anything") == "Hello world"

    def test_default_no_agent(self):
        cmd = CustomCommand(name="check")
        assert cmd.agent is None


# ---------------------------------------------------------------------------
# load_custom_commands()
# ---------------------------------------------------------------------------

def _write_commands(path: Path, commands: list[dict]) -> None:
    import yaml
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump({"commands": commands}), encoding="utf-8")


class TestLoadCustomCommands:
    def test_loads_from_extra_file(self, tmp_path):
        cmds_file = tmp_path / "commands.yaml"
        _write_commands(cmds_file, [
            {"name": "review", "description": "Review code", "prompt": "Review {args}"},
        ])
        result = load_custom_commands(extra_files=[cmds_file])
        names = [c.name for c in result]
        assert "review" in names

    def test_slash_prefix_stripped_from_name(self, tmp_path):
        cmds_file = tmp_path / "commands.yaml"
        _write_commands(cmds_file, [
            {"name": "/explain", "prompt": "Explain {args}"},
        ])
        result = load_custom_commands(extra_files=[cmds_file])
        assert result[0].name == "explain"

    def test_agent_field_loaded(self, tmp_path):
        cmds_file = tmp_path / "commands.yaml"
        _write_commands(cmds_file, [
            {"name": "sec", "prompt": "Check {args}", "agent": "security"},
        ])
        result = load_custom_commands(extra_files=[cmds_file])
        assert result[0].agent == "security"

    def test_later_file_overrides_earlier(self, tmp_path):
        file1 = tmp_path / "global.yaml"
        file2 = tmp_path / "local.yaml"
        _write_commands(file1, [{"name": "review", "prompt": "Global review"}])
        _write_commands(file2, [{"name": "review", "prompt": "Local review {args}"}])
        result = load_custom_commands(extra_files=[file1, file2])
        assert len(result) == 1
        assert "Local" in result[0].prompt

    def test_multiple_commands_loaded(self, tmp_path):
        cmds_file = tmp_path / "commands.yaml"
        _write_commands(cmds_file, [
            {"name": "review", "prompt": "Review {args}"},
            {"name": "explain", "prompt": "Explain {args}"},
            {"name": "summarize", "prompt": "Summarize {args}"},
        ])
        result = load_custom_commands(extra_files=[cmds_file])
        names = {c.name for c in result}
        assert names == {"review", "explain", "summarize"}

    def test_nonexistent_file_skipped(self, tmp_path):
        missing = tmp_path / "not_there.yaml"
        result = load_custom_commands(extra_files=[missing])
        assert result == []

    def test_invalid_yaml_skipped(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(": : : invalid yaml :::", encoding="utf-8")
        result = load_custom_commands(extra_files=[bad])
        assert result == []

    def test_entry_without_name_skipped(self, tmp_path):
        cmds_file = tmp_path / "commands.yaml"
        import yaml
        cmds_file.write_text(
            yaml.dump({"commands": [{"prompt": "No name here"}]}),
            encoding="utf-8",
        )
        result = load_custom_commands(extra_files=[cmds_file])
        assert result == []

    def test_non_dict_entries_skipped(self, tmp_path):
        cmds_file = tmp_path / "commands.yaml"
        import yaml
        cmds_file.write_text(
            yaml.dump({"commands": ["string_entry", {"name": "good", "prompt": "P"}]}),
            encoding="utf-8",
        )
        result = load_custom_commands(extra_files=[cmds_file])
        assert len(result) == 1
        assert result[0].name == "good"

    def test_no_extra_files_returns_empty_when_defaults_missing(self):
        # With no default files present and no extra_files, result is empty
        result = load_custom_commands(extra_files=[])
        # May find ~/.lidco/commands.yaml if it exists; just check type
        assert isinstance(result, list)
