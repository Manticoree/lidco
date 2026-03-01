"""Tests for plan_editor — interactive step-level plan editing."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from lidco.cli.plan_editor import (
    _parse_step_deps,
    _resolve_deps,
    edit_plan_interactively,
    parse_plan_steps,
)


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

    def test_long_plan_shown_in_full(self, console_and_buf) -> None:
        """Plans longer than 3000 chars must not be truncated in the panel."""
        long_plan = "1. " + "x" * 4000  # way over 3000
        console, buf = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="all"):
            edit_plan_interactively(long_plan, console)
        output = buf.getvalue()
        # The full content must appear — not the truncated "..."
        assert "x" * 100 in output  # check a long stretch is present
        # The old truncation sentinel must NOT appear
        assert "x" * 4000 + "..." not in output

    def test_no_steps_long_plan_shown_in_full(self, console_and_buf) -> None:
        """No-steps path returns the full plan without the old [:3000] truncation."""
        long_plan = "This plan has no steps. " + "y" * 4000
        console, _ = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="yes"):
            result = edit_plan_interactively(long_plan, console)
        # The approved plan must be the complete text — not sliced at 3000 chars
        assert result is not None
        assert len(result) == len(long_plan)
        assert "y" * 100 in result


# ── _parse_step_deps ──────────────────────────────────────────────────────────


_PLAN_WITH_DEPS = """\
**Steps:**
1. [Medium | Files: a.py] Do A
   Verify: test A passes
   Deps: none
2. [Easy | Files: b.py] Do B
   Verify: test B passes
   Deps: 1
3. [Hard | Files: c.py] Do C — integration
   Verify: integration test passes
   Deps: 1, 2
"""

_PLAN_NO_DEPS = """\
1. Set up module
2. Add feature
3. Write tests
"""


class TestParseStepDeps:
    def test_no_deps_line_returns_empty_lists(self) -> None:
        deps = _parse_step_deps(_PLAN_NO_DEPS)
        for step_num in (1, 2, 3):
            assert deps.get(step_num, []) == []

    def test_none_deps_returns_empty_list(self) -> None:
        deps = _parse_step_deps(_PLAN_WITH_DEPS)
        assert deps[1] == []

    def test_single_dep_parsed(self) -> None:
        deps = _parse_step_deps(_PLAN_WITH_DEPS)
        assert deps[2] == [1]

    def test_multiple_deps_parsed(self) -> None:
        deps = _parse_step_deps(_PLAN_WITH_DEPS)
        assert set(deps[3]) == {1, 2}

    def test_empty_text_returns_empty(self) -> None:
        assert _parse_step_deps("") == {}

    def test_deps_line_case_insensitive(self) -> None:
        text = "1. Do A\n   DEPS: 2\n2. Do B\n"
        deps = _parse_step_deps(text)
        assert deps.get(1) == [2]

    def test_deps_with_dash_normalise_to_empty(self) -> None:
        text = "1. Step\n   Deps: -\n"
        deps = _parse_step_deps(text)
        assert deps[1] == []


# ── _resolve_deps ─────────────────────────────────────────────────────────────


class TestResolveDeps:
    def test_no_deps_returns_same_set(self) -> None:
        result = _resolve_deps({1, 3}, {1: [], 2: [], 3: []})
        assert result == {1, 3}

    def test_direct_dep_added(self) -> None:
        # step 2 requires step 1; selecting only {2} should pull in 1
        result = _resolve_deps({2}, {1: [], 2: [1]})
        assert 1 in result
        assert 2 in result

    def test_transitive_dep_resolved(self) -> None:
        # 3 → 2 → 1; selecting only {3} should pull in 1 and 2
        result = _resolve_deps({3}, {1: [], 2: [1], 3: [2]})
        assert result == {1, 2, 3}

    def test_already_satisfied_unchanged(self) -> None:
        result = _resolve_deps({1, 2, 3}, {1: [], 2: [1], 3: [1, 2]})
        assert result == {1, 2, 3}

    def test_circular_deps_do_not_loop_forever(self) -> None:
        # Pathological circular deps: 1 → 2 → 1
        result = _resolve_deps({1}, {1: [2], 2: [1]})
        assert 1 in result and 2 in result  # both included, no infinite loop


# ── dependency warning in edit_plan_interactively ────────────────────────────


class TestDepViolationWarning:
    def test_warning_shown_when_deps_violated(self, console_and_buf) -> None:
        console, buf = console_and_buf
        # User selects step 3, which depends on steps 1 and 2 (not selected)
        with patch("rich.prompt.Prompt.ask", side_effect=["1,3", "no"]):
            edit_plan_interactively(_PLAN_WITH_DEPS, console)
        output = buf.getvalue()
        assert "Dependency warnings" in output or "depends on step" in output

    def test_auto_add_deps_on_yes(self, console_and_buf) -> None:
        console, _ = console_and_buf
        # User selects step 3 only; says yes to add deps
        with patch("rich.prompt.Prompt.ask", side_effect=["3", "yes"]):
            result = edit_plan_interactively(_PLAN_WITH_DEPS, console)
        # All three steps should appear since 3 requires 1 and 2
        assert result is not None
        assert "Do A" in result
        assert "Do B" in result
        assert "Do C" in result

    def test_no_auto_add_keeps_original_selection(self, console_and_buf) -> None:
        console, _ = console_and_buf
        # User selects step 3 only; declines to add deps
        with patch("rich.prompt.Prompt.ask", side_effect=["3", "no"]):
            result = edit_plan_interactively(_PLAN_WITH_DEPS, console)
        # Only step 3 (Do C) should be in the result
        assert result is not None
        assert "Do C" in result
        assert "Do A" not in result
        assert "Do B" not in result

    def test_no_warning_when_all_deps_selected(self, console_and_buf) -> None:
        console, buf = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="1,2,3"):
            edit_plan_interactively(_PLAN_WITH_DEPS, console)
        output = buf.getvalue()
        assert "Dependency warnings" not in output

    def test_no_warning_when_no_deps_defined(self, console_and_buf) -> None:
        console, buf = console_and_buf
        with patch("rich.prompt.Prompt.ask", return_value="2,3"):
            edit_plan_interactively(_PLAN_NO_DEPS, console)
        output = buf.getvalue()
        assert "Dependency warnings" not in output
