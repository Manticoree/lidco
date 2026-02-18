"""Tests for Renderer — specifically summary() filtering."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from lidco.cli.renderer import Renderer


@pytest.fixture
def captured_renderer():
    """Create a Renderer that writes to a string buffer for assertion."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    renderer = Renderer(console)
    return renderer, buf


class TestSummaryFiltering:
    """summary() should exclude read-only tools and only show mutations."""

    def test_read_only_tools_excluded(self, captured_renderer):
        renderer, buf = captured_renderer
        tool_calls = [
            {"tool": "file_read", "args": {"path": "src/main.py"}},
            {"tool": "grep", "args": {"pattern": "TODO"}},
            {"tool": "glob", "args": {"pattern": "*.py"}},
        ]
        renderer.summary(tool_calls)
        output = buf.getvalue()
        # No panel should be printed at all
        assert "Summary" not in output
        assert "Read:" not in output
        assert "Searched:" not in output

    def test_write_tools_shown(self, captured_renderer):
        renderer, buf = captured_renderer
        tool_calls = [
            {"tool": "file_write", "args": {"path": "src/new.py"}},
            {"tool": "file_edit", "args": {"path": "src/old.py"}},
        ]
        renderer.summary(tool_calls)
        output = buf.getvalue()
        assert "Summary" in output
        assert "Created: src/new.py" in output
        assert "Edited: src/old.py" in output

    def test_bash_shown(self, captured_renderer):
        renderer, buf = captured_renderer
        tool_calls = [
            {"tool": "bash", "args": {"command": "npm test"}},
        ]
        renderer.summary(tool_calls)
        output = buf.getvalue()
        assert "Ran: npm test" in output

    def test_git_shown(self, captured_renderer):
        renderer, buf = captured_renderer
        tool_calls = [
            {"tool": "git", "args": {"subcommand": "commit"}},
        ]
        renderer.summary(tool_calls)
        output = buf.getvalue()
        assert "Git: commit" in output

    def test_unknown_tool_shown(self, captured_renderer):
        renderer, buf = captured_renderer
        tool_calls = [
            {"tool": "web_search", "args": {"query": "python docs"}},
        ]
        renderer.summary(tool_calls)
        output = buf.getvalue()
        assert "web_search" in output

    def test_mixed_calls_filters_read_only(self, captured_renderer):
        renderer, buf = captured_renderer
        tool_calls = [
            {"tool": "file_read", "args": {"path": "a.py"}},
            {"tool": "grep", "args": {"pattern": "foo"}},
            {"tool": "file_edit", "args": {"path": "a.py"}},
            {"tool": "glob", "args": {"pattern": "*.md"}},
            {"tool": "bash", "args": {"command": "pytest"}},
        ]
        renderer.summary(tool_calls)
        output = buf.getvalue()
        assert "Edited: a.py" in output
        assert "Ran: pytest" in output
        assert "Read:" not in output
        assert "Searched:" not in output

    def test_deduplication(self, captured_renderer):
        renderer, buf = captured_renderer
        tool_calls = [
            {"tool": "file_edit", "args": {"path": "x.py"}},
            {"tool": "file_edit", "args": {"path": "x.py"}},
        ]
        renderer.summary(tool_calls)
        output = buf.getvalue()
        # "Edited: x.py" should appear only once
        assert output.count("Edited: x.py") == 1

    def test_empty_after_filtering_no_panel(self, captured_renderer):
        renderer, buf = captured_renderer
        tool_calls = [
            {"tool": "file_read", "args": {"path": "a.py"}},
            {"tool": "file_read", "args": {"path": "b.py"}},
        ]
        renderer.summary(tool_calls)
        output = buf.getvalue()
        assert "Summary" not in output

    def test_empty_list_no_panel(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.summary([])
        output = buf.getvalue()
        assert "Summary" not in output
