"""Tests for CodeActionProvider — Q64 Task 436."""

from __future__ import annotations

import pytest
from pathlib import Path


class TestCodeActionFields:
    def test_code_action_frozen(self):
        from lidco.cli.code_actions import CodeAction
        action = CodeAction(title="test", kind="refactor", file="f.py", line=1, command_hint="hint")
        assert action.title == "test"
        assert action.kind == "refactor"
        assert action.line == 1

    def test_code_action_immutable(self):
        from lidco.cli.code_actions import CodeAction
        action = CodeAction(title="test", kind="fix", file="f.py", line=5, command_hint="")
        with pytest.raises(Exception):
            action.title = "changed"  # type: ignore[misc]


class TestCodeActionProvider:
    def test_returns_empty_for_missing_file(self):
        from lidco.cli.code_actions import CodeActionProvider
        provider = CodeActionProvider()
        result = provider.get_actions("/nonexistent/file.py", 1)
        assert result == []

    def test_returns_empty_for_out_of_range_line(self, tmp_path):
        from lidco.cli.code_actions import CodeActionProvider
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        provider = CodeActionProvider()
        result = provider.get_actions(str(f), 999)
        assert result == []

    def test_detects_function_definition(self, tmp_path):
        from lidco.cli.code_actions import CodeActionProvider
        f = tmp_path / "test.py"
        f.write_text("def my_function(x):\n    return x\n")
        provider = CodeActionProvider()
        actions = provider.get_actions(str(f), 1)
        titles = [a.title for a in actions]
        assert any("docstring" in t.lower() or "test" in t.lower() for t in titles)

    def test_detects_todo_comment(self, tmp_path):
        from lidco.cli.code_actions import CodeActionProvider
        f = tmp_path / "test.py"
        f.write_text("# TODO: implement this\nx = 1\n")
        provider = CodeActionProvider()
        actions = provider.get_actions(str(f), 1)
        titles = [a.title for a in actions]
        assert any("todo" in t.lower() or "implement" in t.lower() for t in titles)

    def test_detects_fixme_comment(self, tmp_path):
        from lidco.cli.code_actions import CodeActionProvider
        f = tmp_path / "test.py"
        f.write_text("# FIXME: broken here\nx = 1\n")
        provider = CodeActionProvider()
        actions = provider.get_actions(str(f), 1)
        titles = [a.title for a in actions]
        assert any("fixme" in t.lower() or "fix" in t.lower() for t in titles)

    def test_detects_raise_exception(self, tmp_path):
        from lidco.cli.code_actions import CodeActionProvider
        f = tmp_path / "test.py"
        f.write_text("raise Exception('problem')\n")
        provider = CodeActionProvider()
        actions = provider.get_actions(str(f), 1)
        titles = [a.title for a in actions]
        assert any("exception" in t.lower() for t in titles)

    def test_detects_import_line(self, tmp_path):
        from lidco.cli.code_actions import CodeActionProvider
        f = tmp_path / "test.py"
        f.write_text("import os\n")
        provider = CodeActionProvider()
        actions = provider.get_actions(str(f), 1)
        titles = [a.title for a in actions]
        assert any("import" in t.lower() for t in titles)

    def test_detects_bare_except(self, tmp_path):
        from lidco.cli.code_actions import CodeActionProvider
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        provider = CodeActionProvider()
        actions = provider.get_actions(str(f), 3)  # line 3 is "except:"
        titles = [a.title for a in actions]
        assert any("exception" in t.lower() for t in titles)

    def test_plain_line_no_actions(self, tmp_path):
        from lidco.cli.code_actions import CodeActionProvider
        f = tmp_path / "test.py"
        f.write_text("x = 42\n")
        provider = CodeActionProvider()
        actions = provider.get_actions(str(f), 1)
        assert actions == []

    def test_actions_have_command_hint(self, tmp_path):
        from lidco.cli.code_actions import CodeActionProvider
        f = tmp_path / "test.py"
        f.write_text("def compute(a, b):\n    return a + b\n")
        provider = CodeActionProvider()
        actions = provider.get_actions(str(f), 1)
        for action in actions:
            assert isinstance(action.command_hint, str)
