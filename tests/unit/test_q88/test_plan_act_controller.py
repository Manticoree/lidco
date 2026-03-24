"""Tests for PlanActController (T574)."""
from __future__ import annotations
import asyncio
import pytest
from lidco.agents.plan_act_controller import PlanActController, ActionStep, PlanActResult


def test_build_plan():
    ctrl = PlanActController()
    steps = ctrl.build_plan([{"description": "Step A"}, {"description": "Step B"}])
    assert len(steps) == 2
    assert steps[0].index == 1
    assert steps[1].description == "Step B"


def test_format_plan():
    ctrl = PlanActController()
    ctrl.build_plan([{"description": "Do this"}, {"description": "Do that"}])
    fmt = ctrl.format_plan()
    assert "Do this" in fmt
    assert "Do that" in fmt


def test_format_plan_empty():
    ctrl = PlanActController()
    fmt = ctrl.format_plan()
    assert "No plan" in fmt


def test_set_mode_valid():
    ctrl = PlanActController()
    ctrl.set_mode("act")
    assert ctrl.mode == "act"


def test_set_mode_invalid():
    ctrl = PlanActController()
    with pytest.raises(ValueError):
        ctrl.set_mode("invalid")


def test_execute_plan_no_executor():
    ctrl = PlanActController()
    plan = ctrl.build_plan([{"description": "A"}, {"description": "B"}])
    result = asyncio.run(ctrl.execute_plan(auto_approve=True))
    assert result.completed == 2
    assert result.failed == 0


def test_execute_plan_with_executor():
    ran = []
    async def executor(step):
        ran.append(step.index)
        return "ok"
    ctrl = PlanActController(executor=executor)
    plan = ctrl.build_plan([{"description": "X"}, {"description": "Y"}])
    result = asyncio.run(ctrl.execute_plan(auto_approve=True))
    assert ran == [1, 2]
    assert result.success


def test_plan_then_act():
    ctrl = PlanActController()
    raw = [{"description": "T1"}, {"description": "T2"}]
    result = asyncio.run(ctrl.plan_then_act(raw, auto_approve=True))
    assert result.completed == 2


def test_confirm_callback_reject():
    async def reject(steps):
        return False
    ctrl = PlanActController(confirm_callback=reject)
    plan = ctrl.build_plan([{"description": "X"}])
    result = asyncio.run(ctrl.execute_plan(auto_approve=False))
    assert result.completed == 0
    assert all(s.status == "skipped" for s in result.steps)
