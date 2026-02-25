"""Tests for plan_editor — interactive step-level plan editing."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from lidco.cli.plan_editor import edit_plan_interactively, parse_plan_steps


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def console_and_buf():
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=100)
    return console, buf


# ── Sample plan text ──────────────────────────────────────────────────────────

_PLAN_WITH_STEPS = """\
Here is the plan:

1. Set up authentication module
2. Create user model with fields
3. Add login endpoint with JWT
4. Write integration tests
"""

_PLAN_NO_STEPS = """\
This plan has no numbered steps.
Just prose describing what to do.
"""

_PLAN_WITH_STEP_PREFIX = """\
Step 1: Install dependencies
Step 2: Configure database
Step 3: Deploy application
"""


# ── parse_plan_steps ──────────────────────────────────────────────────────────


class TestParsePlanSteps:
    def test_extracts_numbered_steps(self) -> None:
        steps = parse_plan_steps(_PLAN_WITH_STEPS)
        assert len(steps) == 4

    def test_step_content_no_leading_number(self) -> None:
        steps = parse_plan_steps(_PLAN_WITH_STEPS)
        assert steps[0] == "Set up authentication module"
        assert steps[1] == "Create user model with fields"

    def test_step_prefix_format(self) -> None:
        steps = parse_plan_steps(_PLAN_WITH_STEP_PREFIX)
        assert len(steps) == 3
        assert "Install dependencies" in steps[0]

    def test_no_steps_returns_empty_list(self) -> None:
        assert parse_plan_steps(_PLAN_NO_STEPS) == []

    def test_empty_string_returns_empty(self) -> None:
        assert parse_plan_steps("") == []

    def test_strips_step_text(self) -> None:
        steps = parse_plan_steps("1.  extra spaces here  ")
        assert steps[0] == "extra spaces here"

    def test_supports_parenthesis_format(self) -> None:
        steps = parse_plan_steps("1) First step\n2) Second step\n")
        assert len(steps) == 2
        assert steps[0] == "First step"

    def test_ignores_non_step_lines(self) -> None:
        text = "Introduction line\n1. Real step\nMid-text line\n2. Another step\n"
        steps = parse_plan_steps(text)
        assert len(steps) == 2


# ── edit_plan_interactively ───────────────────────────────────────────────────


class TestEditPlanInteractively:
    def test_approve_all_returns_full_plan(self, console_and_buf) -> None:
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="all"):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result == _PLAN_WITH_STEPS

    def test_approve_default_returns_full_plan(self, console_and_buf) -> None:
        """Default answer (empty string) approves all steps."""
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value=""):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result == _PLAN_WITH_STEPS

    def test_none_returns_none(self, console_and_buf) -> None:
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="none"):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result is None

    def test_reject_returns_none(self, console_and_buf) -> None:
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="reject"):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result is None

    def test_select_subset_of_steps(self, console_and_buf) -> None:
        """Selecting steps 1 and 3 returns only those steps."""
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="1,3"):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result is not None
        assert "Set up authentication module" in result
        assert "Add login endpoint with JWT" in result
        assert "Create user model" not in result
        assert "Write integration tests" not in result

    def test_selected_steps_renumbered(self, console_and_buf) -> None:
        """Steps 2 and 4 should be renumbered 1 and 2 in the output."""
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="2,4"):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result is not None
        assert "1. Create user model" in result
        assert "2. Write integration tests" in result

    def test_selecting_nonexistent_step_ignored(self, console_and_buf) -> None:
        """Step 99 doesn't exist — other valid steps still returned."""
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="1,99"):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result is not None
        assert "Set up authentication module" in result

    def test_empty_selection_returns_none(self, console_and_buf) -> None:
        """Selecting step 99 (which doesn't exist) → no steps → None."""
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="99"):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result is None

    def test_range_selection(self, console_and_buf) -> None:
        """Range notation '1-3' selects steps 1, 2, and 3."""
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="1-3"):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result is not None
        assert "Set up authentication module" in result
        assert "Create user model" in result
        assert "Add login endpoint" in result
        assert "Write integration tests" not in result

    def test_no_steps_approve_returns_full_plan(self, console_and_buf) -> None:
        """When plan has no steps, 'yes' returns the full plan text."""
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="yes"):
            result = edit_plan_interactively(_PLAN_NO_STEPS, console)
        assert result == _PLAN_NO_STEPS

    def test_no_steps_reject_returns_none(self, console_and_buf) -> None:
        """When plan has no steps, 'no' rejects the plan."""
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="no"):
            result = edit_plan_interactively(_PLAN_NO_STEPS, console)
        assert result is None

    def test_shows_plan_panel(self, console_and_buf) -> None:
        console, buf = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="all"):
            edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert "Generated Plan" in buf.getvalue()

    def test_shows_numbered_steps_in_output(self, console_and_buf) -> None:
        console, buf = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="all"):
            edit_plan_interactively(_PLAN_WITH_STEPS, console)
        output = buf.getvalue()
        assert "Plan steps:" in output

    def test_invalid_input_approves_all(self, console_and_buf) -> None:
        """Unparseable input (e.g. 'abc') falls back to approve all."""
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="abc"):
            result = edit_plan_interactively(_PLAN_WITH_STEPS, console)
        assert result == _PLAN_WITH_STEPS
