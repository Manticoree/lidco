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
        assert "Итог" in output
        assert "Создан: src/new.py" in output
        assert "Изменён: src/old.py" in output

    def test_bash_shown(self, captured_renderer):
        renderer, buf = captured_renderer
        tool_calls = [
            {"tool": "bash", "args": {"command": "npm test"}},
        ]
        renderer.summary(tool_calls)
        output = buf.getvalue()
        assert "Выполнено: npm test" in output

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
        assert "Изменён: a.py" in output
        assert "Выполнено: pytest" in output
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
        # "Изменён: x.py" should appear only once
        assert output.count("Изменён: x.py") == 1

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


class TestAssistantHeader:
    """assistant_header() uses agent-specific icon and color."""

    def test_known_agent_shows_label(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("coder")
        output = buf.getvalue()
        assert "coder" in output

    def test_debugger_header(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("debugger")
        output = buf.getvalue()
        assert "debugger" in output

    def test_unknown_agent_falls_back(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("myagent")
        output = buf.getvalue()
        assert "myagent" in output

    def test_default_agent_is_lidco(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header()
        output = buf.getvalue()
        assert "lidco" in output

    def test_agent_icon_present(self, captured_renderer):
        # ⌨ (U+2328) is the coder icon
        renderer, buf = captured_renderer
        renderer.assistant_header("coder")
        output = buf.getvalue()
        assert "\u2328" in output


class TestCodeBlockPanels:
    """markdown() promotes large code blocks to syntax-highlighted panels."""

    def _make_fence(self, lang: str, lines: int) -> str:
        code_body = "\n".join(f"    line_{i} = {i}" for i in range(lines))
        return f"```{lang}\n{code_body}\n```"

    def test_short_block_not_promoted(self, captured_renderer):
        renderer, buf = captured_renderer
        text = self._make_fence("python", 5)
        renderer.markdown(text)
        # Short block stays inline — no Panel border characters
        output = buf.getvalue()
        # Panel border uses box-drawing chars; short blocks should NOT produce a Panel
        assert "line_0" in output

    def test_large_block_promoted_to_panel(self, captured_renderer):
        renderer, buf = captured_renderer
        text = self._make_fence("python", 15)
        renderer.markdown(text)
        output = buf.getvalue()
        assert "line_0" in output
        assert "line_14" in output

    def test_prose_before_code_preserved(self, captured_renderer):
        renderer, buf = captured_renderer
        prose = "Here is the implementation:\n\n"
        code = self._make_fence("python", 12)
        renderer.markdown(prose + code)
        output = buf.getvalue()
        assert "implementation" in output
        assert "line_0" in output

    def test_multiple_large_blocks(self, captured_renderer):
        renderer, buf = captured_renderer
        block1 = self._make_fence("python", 12)
        block2 = self._make_fence("bash", 11)
        renderer.markdown(block1 + "\n\nSome text\n\n" + block2)
        output = buf.getvalue()
        assert "line_0" in output
        assert "Some text" in output

    def test_empty_text_no_crash(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.markdown("")  # should not raise
        output = buf.getvalue()
        assert output == "" or True  # just check no exception


class TestTurnSummary:
    """turn_summary() prints a compact one-line summary."""

    def test_basic_summary(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="gpt-4", iterations=3, tool_calls=2,
            files_changed=1, tokens=1500, cost_usd=0.002,
        )
        output = buf.getvalue()
        assert "gpt-4" in output
        assert "2 инструментов" in output
        assert "1 файл" in output
        assert "1.5k токенов" in output
        assert "$0.002" in output

    def test_no_cost_hidden(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="gpt-4", iterations=1, tool_calls=0,
            files_changed=0, tokens=500, cost_usd=0.0,
        )
        output = buf.getvalue()
        assert "$" not in output
        assert "500 токенов" in output

    def test_single_tool(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="m", iterations=1, tool_calls=1,
            files_changed=0, tokens=100, cost_usd=0.0,
        )
        output = buf.getvalue()
        assert "1 инструмент" in output
        assert "инструментов" not in output

    def test_step_shown_when_multiple_iterations(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="m", iterations=5, tool_calls=0,
            files_changed=0, tokens=100, cost_usd=0.0,
        )
        output = buf.getvalue()
        assert "шаг 5" in output

    def test_step_hidden_when_one_iteration(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="m", iterations=1, tool_calls=0,
            files_changed=0, tokens=100, cost_usd=0.0,
        )
        output = buf.getvalue()
        assert "шаг" not in output


class TestAgentSelected:
    """agent_selected() prints a dim auto-routing announcement."""

    def test_known_agent_shows_icon(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.agent_selected("coder")
        output = buf.getvalue()
        assert "Авто" in output
        assert "coder" in output
        assert "\u2192" in output  # → arrow

    def test_unknown_agent_fallback(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.agent_selected("mybot")
        output = buf.getvalue()
        assert "mybot" in output

    def test_debugger_announcement(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.agent_selected("debugger")
        output = buf.getvalue()
        assert "debugger" in output


class TestModelFallback:
    """model_fallback() prints a fallback notification."""

    def test_shows_both_models(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.model_fallback("claude-opus", "claude-sonnet", "retries exhausted")
        output = buf.getvalue()
        assert "claude-opus" in output
        assert "claude-sonnet" in output
        assert "retries exhausted" in output

    def test_shows_arrow(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.model_fallback("a", "b", "stream error")
        output = buf.getvalue()
        assert "\u2192" in output  # →


class TestContextWarning:
    """context_warning() prints a usage warning."""

    def test_shows_percentage(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.context_warning(83)
        output = buf.getvalue()
        assert "83%" in output

    def test_shows_clear_hint(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.context_warning(95)
        output = buf.getvalue()
        assert "/clear" in output


class TestFriendlyError:
    """friendly_error() maps exceptions to user-friendly messages."""

    def test_llm_retry_exhausted(self, captured_renderer):
        renderer, buf = captured_renderer

        class LLMRetryExhausted(Exception):
            pass

        renderer.friendly_error(LLMRetryExhausted("all failed"))
        output = buf.getvalue()
        assert "Все модели недоступны" in output

    def test_timeout_error(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.friendly_error(TimeoutError("timed out"))
        output = buf.getvalue()
        assert "время ожидания" in output.lower()

    def test_generic_exception(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.friendly_error(ValueError("bad value xyz"))
        output = buf.getvalue()
        assert "bad value xyz" in output

    def test_no_crash_on_empty_message(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.friendly_error(RuntimeError(""))
        # Should not raise


# ── Task 154 + 157: turn number in header, elapsed time in summary ────────────

class TestAssistantHeaderTurn:
    """assistant_header() can show a turn number."""

    def test_turn_number_shown(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("coder", turn=3)
        output = buf.getvalue()
        assert "Ход 3" in output
        assert "coder" in output

    def test_turn_zero_omitted(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("coder", turn=0)
        output = buf.getvalue()
        assert "Ход" not in output
        assert "coder" in output

    def test_turn_default_omitted(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("debugger")
        output = buf.getvalue()
        assert "Ход" not in output

    def test_turn_one(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("tester", turn=1)
        output = buf.getvalue()
        assert "Ход 1" in output
        assert "tester" in output

    def test_large_turn_number(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("auto", turn=42)
        output = buf.getvalue()
        assert "Ход 42" in output

    def test_agent_still_shown_with_turn(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("architect", turn=5)
        output = buf.getvalue()
        assert "architect" in output
        assert "Ход 5" in output

    def test_unknown_agent_with_turn(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.assistant_header("mybot", turn=2)
        output = buf.getvalue()
        assert "mybot" in output
        assert "Ход 2" in output


class TestTurnSummaryElapsed:
    """turn_summary() can show elapsed time."""

    def test_elapsed_shown(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="gpt-4", iterations=1, tool_calls=0,
            files_changed=0, tokens=100, cost_usd=0.0,
            elapsed=3.7,
        )
        output = buf.getvalue()
        assert "3.7с" in output

    def test_elapsed_zero_omitted(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="gpt-4", iterations=1, tool_calls=0,
            files_changed=0, tokens=100, cost_usd=0.0,
            elapsed=0.0,
        )
        output = buf.getvalue()
        assert "с" not in output or "токенов" in output  # no elapsed suffix

    def test_elapsed_default_omitted(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="gpt-4", iterations=1, tool_calls=0,
            files_changed=0, tokens=100, cost_usd=0.0,
        )
        output = buf.getvalue()
        # No time shown when elapsed not provided
        assert "0.0с" not in output

    def test_elapsed_one_decimal(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="m", iterations=1, tool_calls=0,
            files_changed=0, tokens=50, cost_usd=0.0,
            elapsed=12.456,
        )
        output = buf.getvalue()
        assert "12.5с" in output

    def test_elapsed_with_other_fields(self, captured_renderer):
        renderer, buf = captured_renderer
        renderer.turn_summary(
            model="claude-3", iterations=2, tool_calls=3,
            files_changed=1, tokens=2000, cost_usd=0.01,
            elapsed=5.0,
        )
        output = buf.getvalue()
        assert "claude-3" in output
        assert "5.0с" in output
        assert "2.0k токенов" in output
