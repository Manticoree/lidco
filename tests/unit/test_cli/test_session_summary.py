"""Tests for _show_session_summary helper."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from lidco.cli.app import _show_session_summary


@pytest.fixture
def console_and_buf():
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=80)
    return console, buf


class TestShowSessionSummary:
    def test_no_output_when_zero_turns(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=0, tokens=0, cost_usd=0.0, tool_calls=0, files_edited=set())
        assert buf.getvalue() == ""

    def test_shows_turns(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=3, tokens=100, cost_usd=0.0, tool_calls=0, files_edited=set())
        assert "3" in buf.getvalue()
        assert "Turn" in buf.getvalue()

    def test_shows_token_count(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=1, tokens=2500, cost_usd=0.0, tool_calls=0, files_edited=set())
        output = buf.getvalue()
        assert "2.5k" in output

    def test_shows_small_token_count(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=1, tokens=500, cost_usd=0.0, tool_calls=0, files_edited=set())
        output = buf.getvalue()
        assert "500" in output

    def test_shows_cost_when_nonzero(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.0042, tool_calls=0, files_edited=set())
        output = buf.getvalue()
        assert "$0.0042" in output

    def test_small_cost_uses_more_decimal_places(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.000015, tool_calls=0, files_edited=set())
        output = buf.getvalue()
        # Should show full precision (not rounded to 4 dp which gives $0.0000)
        assert "0.000015" in output

    def test_hides_cost_when_zero(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.0, tool_calls=0, files_edited=set())
        assert "$" not in buf.getvalue()

    def test_shows_tool_calls_when_nonzero(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=2, tokens=300, cost_usd=0.0, tool_calls=5, files_edited=set())
        output = buf.getvalue()
        assert "5" in output
        assert "Tool" in output

    def test_hides_tool_calls_when_zero(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.0, tool_calls=0, files_edited=set())
        assert "Tool" not in buf.getvalue()

    def test_shows_files_edited_count(self, console_and_buf):
        console, buf = console_and_buf
        files = {"src/a.py", "src/b.py"}
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.0, tool_calls=2, files_edited=files)
        output = buf.getvalue()
        assert "2" in output
        assert "Files" in output

    def test_lists_file_paths(self, console_and_buf):
        console, buf = console_and_buf
        files = {"src/a.py", "src/b.py"}
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.0, tool_calls=2, files_edited=files)
        output = buf.getvalue()
        assert "src/a.py" in output
        assert "src/b.py" in output
        # Files should be sorted
        assert output.index("src/a.py") < output.index("src/b.py")

    def test_truncates_many_files(self, console_and_buf):
        console, buf = console_and_buf
        files = {f"src/f{i}.py" for i in range(10)}
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.0, tool_calls=10, files_edited=files)
        output = buf.getvalue()
        assert "more" in output

    def test_exactly_5_files_no_more_text(self, console_and_buf):
        console, buf = console_and_buf
        files = {f"src/f{i}.py" for i in range(5)}
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.0, tool_calls=5, files_edited=files)
        assert "more" not in buf.getvalue()

    def test_6_files_shows_1_more(self, console_and_buf):
        console, buf = console_and_buf
        files = {f"src/f{i}.py" for i in range(6)}
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.0, tool_calls=6, files_edited=files)
        assert "1 more" in buf.getvalue()

    def test_summary_panel_title(self, console_and_buf):
        console, buf = console_and_buf
        _show_session_summary(console, turns=1, tokens=100, cost_usd=0.0, tool_calls=0, files_edited=set())
        assert "Session Summary" in buf.getvalue()
