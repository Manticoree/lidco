"""Tests for StreamDisplay component."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock

import pytest
from rich.console import Console

from lidco.cli.stream_display import StreamDisplay, _brief_result, _extract_key_arg


@pytest.fixture
def captured_console():
    """Create a Console that writes to a string buffer for assertion."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    return console, buf


@pytest.fixture
def display(captured_console):
    console, _ = captured_console
    sd = StreamDisplay(console)
    yield sd
    sd.finish()


class TestOnTextChunk:
    def test_prints_text_inline(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        sd.on_text_chunk("Hello ")
        sd.on_text_chunk("world")
        sd.finish()
        output = buf.getvalue()
        assert "Hello " in output
        assert "world" in output

    def test_empty_text_ignored(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        sd.on_text_chunk("")
        sd.finish()
        assert not sd._has_content

    def test_has_content_flag(self, display):
        assert not display._has_content
        display.on_text_chunk("hi")
        assert display._has_content


class TestReadOnlyTools:
    """Read-only tools (file_read, glob, grep) show dim inline marker on start, silent on end."""

    @pytest.mark.parametrize(
        "tool,args,expected_text",
        [
            ("file_read", {"path": "src/main.py"}, "Reading src/main.py"),
            ("glob", {"pattern": "*.py"}, "Matching *.py"),
            ("grep", {"pattern": "TODO"}, "Searching for TODO"),
        ],
    )
    def test_start_shows_inline_marker(self, captured_console, tool, args, expected_text):
        console, buf = captured_console
        sd = StreamDisplay(console)
        sd.on_tool_event("start", tool, args)
        sd.finish()
        output = buf.getvalue()
        assert "\u21b3" in output
        assert expected_text in output
        # Should NOT show lightning bolt
        assert "\u26a1" not in output

    @pytest.mark.parametrize("tool", ["file_read", "glob", "grep"])
    def test_end_event_silenced(self, captured_console, tool):
        console, buf = captured_console
        sd = StreamDisplay(console)
        result = MagicMock()
        result.success = True
        result.output = "some output"
        sd.on_tool_event("end", tool, {}, result)
        sd.finish()
        output = buf.getvalue()
        assert "\u2713" not in output

    def test_non_read_only_tool_still_shown(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        sd.on_tool_event("start", "git", {"subcommand": "status"})
        sd.finish()
        output = buf.getvalue()
        assert "\u26a1" in output
        assert "git" in output


class TestFileEditDisplay:
    """file_edit should show a compact diff."""

    def test_shows_diff_lines(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        args = {
            "path": "src/app.py",
            "old_string": "old line 1\nold line 2",
            "new_string": "new line 1\nnew line 2",
        }
        result = MagicMock()
        result.success = True
        result.output = "Replaced 1 occurrence(s)"
        sd.on_tool_event("end", "file_edit", args, result)
        sd.finish()
        output = buf.getvalue()
        assert "\u270f" in output
        assert "src/app.py" in output
        assert "old line 1" in output
        assert "new line 1" in output
        assert "\u2713" in output

    def test_truncates_long_diffs(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        old_lines = "\n".join(f"old line {i}" for i in range(20))
        new_lines = "\n".join(f"new line {i}" for i in range(20))
        args = {
            "path": "big.py",
            "old_string": old_lines,
            "new_string": new_lines,
        }
        result = MagicMock()
        result.success = True
        result.output = "Applied"
        sd.on_tool_event("end", "file_edit", args, result)
        sd.finish()
        output = buf.getvalue()
        # Should show "... (10 more lines)" for both old and new
        assert "10 more lines" in output

    def test_edit_start_not_shown_as_lightning(self, captured_console):
        """file_edit start should still show (it's not in _READ_ONLY_TOOLS)."""
        console, buf = captured_console
        sd = StreamDisplay(console)
        sd.on_tool_event("start", "file_edit", {"path": "f.py"})
        sd.finish()
        output = buf.getvalue()
        assert "\u26a1" in output
        assert "file_edit" in output


class TestFileWriteDisplay:
    """file_write should show path and line count."""

    def test_shows_created_file(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        content = "line1\nline2\nline3\n"
        args = {"path": "src/new_file.py", "content": content}
        result = MagicMock()
        result.success = True
        result.output = "created"
        sd.on_tool_event("end", "file_write", args, result)
        sd.finish()
        output = buf.getvalue()
        assert "\u270f" in output
        assert "Created src/new_file.py" in output
        assert "3 lines" in output

    def test_single_line_file(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        args = {"path": "one.txt", "content": "single line"}
        result = MagicMock()
        result.success = True
        result.output = "created"
        sd.on_tool_event("end", "file_write", args, result)
        sd.finish()
        output = buf.getvalue()
        assert "1 lines" in output


class TestBashDisplay:
    """bash should show command on start and output on end."""

    def test_start_shows_dollar_prompt(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        sd.on_tool_event("start", "bash", {"command": "npm test"})
        sd.finish()
        output = buf.getvalue()
        assert "$ " in output
        assert "npm test" in output
        # Should NOT show lightning bolt for bash
        assert "\u26a1" not in output

    def test_end_shows_output_lines(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        result = MagicMock()
        result.success = True
        result.output = "PASS src/app.test.ts\nTests: 5 passed"
        sd.on_tool_event("end", "bash", {"command": "npm test"}, result)
        sd.finish()
        output = buf.getvalue()
        assert "PASS src/app.test.ts" in output
        assert "Tests: 5 passed" in output

    def test_end_truncates_long_output(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        result = MagicMock()
        result.success = True
        result.output = "\n".join(f"line {i}" for i in range(30))
        sd.on_tool_event("end", "bash", {"command": "ls"}, result)
        sd.finish()
        output = buf.getvalue()
        assert "15 more lines" in output

    def test_bash_error_shows_error(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        result = MagicMock()
        result.success = False
        result.error = "Command failed"
        sd.on_tool_event("end", "bash", {"command": "bad"}, result)
        sd.finish()
        output = buf.getvalue()
        assert "\u2717" in output
        assert "Command failed" in output


class TestOnToolEvent:
    """General tool event tests for non-special tools."""

    def test_end_event_failure(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        result = MagicMock()
        result.success = False
        result.error = "Something went wrong"
        sd.on_tool_event("end", "git", {"subcommand": "push"}, result)
        sd.finish()
        output = buf.getvalue()
        assert "\u2717" in output
        assert "Something went wrong" in output

    def test_generic_tool_start(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        sd.on_tool_event("start", "web_search", {"query": "python docs"})
        sd.finish()
        output = buf.getvalue()
        assert "\u26a1" in output
        assert "web_search" in output


class TestOnStatus:
    def test_updates_status_bar_label(self, captured_console):
        console, _ = captured_console
        sd = StreamDisplay(console)
        sd.on_status("Routing")
        assert sd._status_bar.label == "Routing"
        sd.finish()

    def test_updates_label_on_subsequent_calls(self, captured_console):
        console, _ = captured_console
        sd = StreamDisplay(console)
        sd.on_status("Routing")
        sd.on_status("Thinking (step 1)")
        assert sd._status_bar.label == "Thinking (step 1)"
        sd.finish()

    def test_live_starts_immediately(self, captured_console):
        console, _ = captured_console
        sd = StreamDisplay(console)
        assert sd.live is not None
        sd.finish()

    def test_live_none_after_finish(self, captured_console):
        console, _ = captured_console
        sd = StreamDisplay(console)
        sd.finish()
        assert sd.live is None


class TestUpdateTokens:
    def test_updates_token_count(self, captured_console):
        console, _ = captured_console
        sd = StreamDisplay(console)
        sd.update_tokens(1500)
        assert sd._status_bar.total_tokens == 1500
        sd.finish()

    def test_zero_tokens_hidden(self, captured_console):
        console, _ = captured_console
        sd = StreamDisplay(console)
        assert sd._status_bar.total_tokens == 0
        sd.finish()


class TestFinish:
    def test_adds_newline_when_needed(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)
        sd.on_text_chunk("no newline")
        assert sd._needs_newline
        sd.finish()
        assert not sd._needs_newline

    def test_stops_live(self, captured_console):
        console, _ = captured_console
        sd = StreamDisplay(console)
        assert sd._live is not None
        sd.finish()
        assert sd._live is None


class TestStatusBarLifecycle:
    """Test the full status bar lifecycle across multiple phases."""

    def test_status_bar_persists_through_interaction(self, captured_console):
        console, buf = captured_console
        sd = StreamDisplay(console)

        sd.on_status("Thinking (step 1)")
        assert sd.live is not None

        sd.on_text_chunk("Let me check. ")
        assert sd.live is not None

        # file_read shows only a dim marker, but bar should still be there
        sd.on_tool_event("start", "file_read", {"path": "x.py"})
        assert sd.live is not None

        result = MagicMock()
        result.success = True
        result.output = "content\n"
        sd.on_tool_event("end", "file_read", {"path": "x.py"}, result)

        sd.on_status("Thinking (step 2)")
        assert sd.live is not None

        sd.update_tokens(500)
        assert sd._status_bar.total_tokens == 500

        sd.on_text_chunk("Done.")
        sd.finish()
        assert sd.live is None


class TestExtractKeyArg:
    def test_file_tools(self):
        assert _extract_key_arg("file_read", {"path": "src/x.py"}) == "src/x.py"
        assert _extract_key_arg("file_write", {"path": "out.txt"}) == "out.txt"
        assert _extract_key_arg("file_edit", {"path": "f.py"}) == "f.py"

    def test_bash(self):
        assert _extract_key_arg("bash", {"command": "ls -la"}) == "ls -la"

    def test_bash_truncation(self):
        long_cmd = "x" * 100
        result = _extract_key_arg("bash", {"command": long_cmd})
        assert len(result) <= 63
        assert result.endswith("...")

    def test_search_tools(self):
        assert _extract_key_arg("grep", {"pattern": "TODO"}) == "TODO"
        assert _extract_key_arg("glob", {"pattern": "*.py"}) == "*.py"

    def test_git(self):
        assert _extract_key_arg("git", {"subcommand": "status"}) == "status"

    def test_unknown_tool(self):
        assert _extract_key_arg("custom_tool", {"foo": "bar"}) == ""


class TestBriefResult:
    def test_file_read(self):
        result = MagicMock()
        result.output = "line1\nline2\nline3\n"
        assert _brief_result("file_read", result) == "3 lines"

    def test_file_write(self):
        result = MagicMock()
        result.output = "created"
        assert _brief_result("file_write", result) == "Applied edit"

    def test_bash_single_line(self):
        result = MagicMock()
        result.output = "OK"
        assert _brief_result("bash", result) == "OK"

    def test_bash_multi_line(self):
        result = MagicMock()
        result.output = "line1\nline2\nline3"
        assert _brief_result("bash", result) == "3 lines of output"

    def test_grep_matches(self):
        result = MagicMock()
        result.output = "file1.py\nfile2.py\n"
        assert _brief_result("grep", result) == "2 matches"
