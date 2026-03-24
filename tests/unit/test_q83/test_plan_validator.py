"""Tests for PlanValidator (T543)."""
from __future__ import annotations
import asyncio
import pytest
from lidco.agents.plan_validator import PlanValidator, PlanStep, ValidationResult


PLAN = """
1. Install dependencies
2. Run migrations
3. Deploy to staging
"""


def test_parse_steps_basic():
    v = PlanValidator()
    steps = v.parse_steps(PLAN)
    assert len(steps) == 3
    assert steps[0].index == 1
    assert "Install" in steps[0].description


def test_parse_steps_paren_format():
    v = PlanValidator()
    steps = v.parse_steps("1) Do this\n2) Do that\n")
    assert len(steps) == 2


def test_parse_steps_empty():
    v = PlanValidator()
    steps = v.parse_steps("No numbered steps here")
    assert steps == []


def test_format_plan():
    v = PlanValidator()
    steps = v.parse_steps(PLAN)
    formatted = v.format_plan(steps)
    assert "Install dependencies" in formatted
    assert "Plan:" in formatted


def test_validate_auto_approve():
    v = PlanValidator()
    result = asyncio.run(v.validate(PLAN, auto_approve=True))
    assert result.approved is True
    assert all(s.status == "approved" for s in result.steps)


def test_validate_no_callback_auto_approves():
    v = PlanValidator(confirm_callback=None)
    result = asyncio.run(v.validate(PLAN))
    assert result.approved is True


def test_validate_callback_reject():
    async def reject(plan_text):
        return False
    v = PlanValidator(confirm_callback=reject)
    result = asyncio.run(v.validate(PLAN))
    assert result.approved is False
    assert all(s.status == "skipped" for s in result.steps)


def test_apply_edits():
    v = PlanValidator()
    steps = v.parse_steps(PLAN)
    edited = v.apply_edits(steps, {1: "Install new deps"})
    assert edited[0].description == "Install new deps"
    assert edited[1].description == steps[1].description


def test_skip_steps():
    v = PlanValidator()
    steps = v.parse_steps(PLAN)
    skipped = v.skip_steps(steps, [2])
    assert skipped[1].status == "skipped"
    assert skipped[0].status == "pending"


def test_approved_steps_filters_skipped():
    v = PlanValidator()
    steps = v.parse_steps(PLAN)
    skipped = v.skip_steps(steps, [2])
    result = ValidationResult(approved=True, steps=skipped)
    assert len(result.approved_steps) == 2
