"""Tests for HorizonPlanner (T580)."""
import asyncio
import json
import tempfile
from pathlib import Path
import pytest
from lidco.tasks.horizon_planner import (
    HorizonPlanner,
    PlanStep,
    StepStatus,
    PhaseStatus,
)


async def simple_runner(step: PlanStep) -> str:
    return f"completed {step.id}"


async def failing_runner(step: PlanStep) -> str:
    raise RuntimeError(f"step {step.id} failed")


def make_planner(**kwargs) -> HorizonPlanner:
    return HorizonPlanner(step_runner=simple_runner, **kwargs)


def test_add_phase_and_format():
    p = make_planner()
    p.set_goal("Build a service")
    p.add_phase("setup", [("s1", "Install deps"), ("s2", "Configure env")])
    plan = p.format_plan()
    assert "Build a service" in plan
    assert "setup" in plan
    assert "Install deps" in plan
    assert "Configure env" in plan


def test_run_success():
    p = make_planner()
    p.set_goal("Simple goal")
    p.add_phase("only", [("s1", "Do thing")])
    result = asyncio.run(p.run())
    assert result.success
    assert result.steps_done == 1
    assert result.steps_failed == 0
    assert result.phases_done == 1


def test_run_multi_phase_success():
    p = make_planner()
    p.set_goal("Multi phase")
    p.add_phase("phase1", [("s1", "step 1"), ("s2", "step 2")])
    p.add_phase("phase2", [("s3", "step 3")])
    result = asyncio.run(p.run())
    assert result.success
    assert result.steps_done == 3
    assert result.phases_done == 2


def test_run_failure_stops_phases():
    p = HorizonPlanner(step_runner=failing_runner, max_retries=0, backoff_base=0.0)
    p.set_goal("Failing goal")
    p.add_phase("bad", [("s1", "Bad step")])
    p.add_phase("unreachable", [("s2", "Should not run")])
    result = asyncio.run(p.run())
    assert not result.success
    assert result.steps_failed == 1


def test_step_retry_on_failure():
    call_counts: dict[str, int] = {}

    async def flaky_runner(step: PlanStep) -> str:
        call_counts[step.id] = call_counts.get(step.id, 0) + 1
        if call_counts[step.id] < 2:
            raise RuntimeError("transient")
        return "ok"

    p = HorizonPlanner(step_runner=flaky_runner, max_retries=2, backoff_base=0.0)
    p.set_goal("Flaky goal")
    p.add_phase("phase", [("s1", "Flaky step")])
    result = asyncio.run(p.run())
    assert result.success
    assert call_counts["s1"] == 2


def test_rollback_called_on_phase_failure():
    rolled_back: list[str] = []

    async def rollback(phase) -> None:
        rolled_back.append(phase.name)

    p = HorizonPlanner(step_runner=failing_runner, rollback_fn=rollback, max_retries=0, backoff_base=0.0)
    p.set_goal("Rollback test")
    p.add_phase("failing_phase", [("s1", "fail")])
    asyncio.run(p.run())
    assert "failing_phase" in rolled_back


def test_confirm_fn_abort():
    async def deny_all(phase) -> bool:
        return False

    p = HorizonPlanner(step_runner=simple_runner, confirm_fn=deny_all)
    p.set_goal("Blocked goal")
    p.add_phase("phase", [("s1", "step")])
    result = asyncio.run(p.run())
    assert not result.success


def test_checkpoint_resume(tmp_path):
    ckpt = tmp_path / "ckpt.json"

    # First run: add phases but fail on phase 2
    call_counter = {"n": 0}

    async def partial_runner(step: PlanStep) -> str:
        call_counter["n"] += 1
        if step.phase == "phase2":
            raise RuntimeError("fail phase2")
        return "ok"

    p = HorizonPlanner(
        step_runner=partial_runner,
        checkpoint_path=ckpt,
        max_retries=0,
        backoff_base=0.0,
    )
    p.set_goal("Resume test")
    p.add_phase("phase1", [("s1", "step1")])
    p.add_phase("phase2", [("s2", "step2")])
    result1 = asyncio.run(p.run())
    assert not result1.success
    assert ckpt.exists()

    # Second run: fix phase2 runner, resume
    async def fixed_runner(step: PlanStep) -> str:
        return "ok fixed"

    p2 = HorizonPlanner(step_runner=fixed_runner, checkpoint_path=ckpt, max_retries=0, backoff_base=0.0)
    p2.set_goal("Resume test")
    p2.add_phase("phase1", [("s1", "step1")])
    p2.add_phase("phase2", [("s2", "step2")])
    result2 = asyncio.run(p2.run(resume=True))
    assert result2.resumed


def test_no_runner_simulation():
    p = HorizonPlanner()  # no step_runner
    p.set_goal("Simulated goal")
    p.add_phase("sim", [("s1", "sim step")])
    result = asyncio.run(p.run())
    assert result.success  # simulation always succeeds


def test_elapsed_positive():
    p = make_planner()
    p.set_goal("Timing test")
    p.add_phase("phase", [("s1", "step")])
    result = asyncio.run(p.run())
    assert result.elapsed >= 0


def test_phase_status_after_success():
    p = make_planner()
    p.set_goal("Phase status")
    p.add_phase("only", [("s1", "step")])
    asyncio.run(p.run())
    assert p._phases[0].status == PhaseStatus.DONE


def test_phase_status_after_failure():
    p = HorizonPlanner(step_runner=failing_runner, max_retries=0, backoff_base=0.0)
    p.set_goal("Fail status")
    p.add_phase("bad", [("s1", "bad")])
    asyncio.run(p.run())
    # phase should be FAILED or ROLLED_BACK
    assert p._phases[0].status in (PhaseStatus.FAILED, PhaseStatus.ROLLED_BACK)
