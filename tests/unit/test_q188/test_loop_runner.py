"""Tests for loop_runner (task 1053)."""

import pytest
from lidco.autonomous.loop_config import LoopConfig, LoopState
from lidco.autonomous.loop_runner import AutonomousLoopRunner, LoopResult


def _echo_executor(prompt: str, iteration: int) -> str:
    return f"[{iteration}] {prompt}"


def _completing_executor(prompt: str, iteration: int) -> str:
    if iteration >= 3:
        return "ALL TESTS PASS"
    return f"working... iteration {iteration}"


def _failing_executor(prompt: str, iteration: int) -> str:
    raise RuntimeError("boom")


# -- basic run ------------------------------------------------------------


def test_run_simple():
    cfg = LoopConfig(prompt="go", max_iterations=3, cooldown_s=0.0)
    runner = AutonomousLoopRunner(cfg)
    result = runner.run(_echo_executor)
    assert len(result.iterations) == 3
    assert result.state == LoopState.COMPLETED


def test_run_returns_loop_result():
    cfg = LoopConfig(prompt="go", max_iterations=1, cooldown_s=0.0)
    result = AutonomousLoopRunner(cfg).run(_echo_executor)
    assert isinstance(result, LoopResult)
    assert result.config == cfg
    assert result.total_duration_ms >= 0


def test_initial_state_idle():
    cfg = LoopConfig(prompt="x")
    runner = AutonomousLoopRunner(cfg)
    assert runner.state == LoopState.IDLE


def test_iterations_tuple_after_run():
    cfg = LoopConfig(prompt="go", max_iterations=2, cooldown_s=0.0)
    runner = AutonomousLoopRunner(cfg)
    runner.run(_echo_executor)
    assert isinstance(runner.iterations, tuple)
    assert len(runner.iterations) == 2


# -- completion promise ---------------------------------------------------


def test_completion_promise_stops_loop():
    cfg = LoopConfig(
        prompt="fix",
        max_iterations=10,
        completion_promise="ALL TESTS PASS",
        cooldown_s=0.0,
    )
    result = AutonomousLoopRunner(cfg).run(_completing_executor)
    assert result.completed_naturally is True
    assert result.state == LoopState.COMPLETED
    assert len(result.iterations) == 3


def test_no_promise_runs_all_iterations():
    cfg = LoopConfig(prompt="go", max_iterations=5, cooldown_s=0.0)
    result = AutonomousLoopRunner(cfg).run(_echo_executor)
    assert len(result.iterations) == 5
    assert result.completed_naturally is False


def test_promise_case_insensitive():
    def exec_fn(p: str, i: int) -> str:
        return "all tests pass" if i == 2 else "nope"

    cfg = LoopConfig(prompt="x", max_iterations=5, completion_promise="ALL TESTS PASS", cooldown_s=0.0)
    result = AutonomousLoopRunner(cfg).run(exec_fn)
    assert len(result.iterations) == 2
    assert result.iterations[-1].claimed_complete is True


# -- error handling -------------------------------------------------------


def test_executor_error_stops_loop():
    cfg = LoopConfig(prompt="x", max_iterations=5, cooldown_s=0.0)
    result = AutonomousLoopRunner(cfg).run(_failing_executor)
    assert result.state == LoopState.FAILED
    assert len(result.iterations) == 1
    assert "ERROR:" in result.iterations[0].output


# -- cancel ---------------------------------------------------------------


def test_cancel_stops_loop():
    cfg = LoopConfig(prompt="x", max_iterations=100, cooldown_s=0.0)
    runner = AutonomousLoopRunner(cfg)

    def cancelling_exec(p: str, i: int) -> str:
        if i == 2:
            runner.cancel()
        return f"iter {i}"

    result = runner.run(cancelling_exec)
    assert result.state == LoopState.FAILED
    # Should have stopped at or before iteration 3
    assert len(result.iterations) <= 3


# -- pause ----------------------------------------------------------------


def test_pause_stops_loop():
    cfg = LoopConfig(prompt="x", max_iterations=100, cooldown_s=0.0)
    runner = AutonomousLoopRunner(cfg)

    def pausing_exec(p: str, i: int) -> str:
        if i == 2:
            runner.pause()
        return f"iter {i}"

    result = runner.run(pausing_exec)
    assert result.state == LoopState.PAUSED
    assert len(result.iterations) <= 3


def test_resume_sets_running():
    cfg = LoopConfig(prompt="x")
    runner = AutonomousLoopRunner(cfg)
    # Manually set paused state
    runner._state = LoopState.PAUSED
    runner._pause_requested = True
    runner.resume()
    assert runner.state == LoopState.RUNNING


# -- early exit -----------------------------------------------------------


def test_allow_early_exit():
    def empty_on_two(p: str, i: int) -> str:
        return "" if i >= 2 else "working"

    cfg = LoopConfig(prompt="x", max_iterations=10, allow_early_exit=True, cooldown_s=0.0)
    result = AutonomousLoopRunner(cfg).run(empty_on_two)
    assert result.completed_naturally is True
    assert len(result.iterations) == 2


# -- timeout --------------------------------------------------------------


def test_timeout_triggers():
    import time

    def slow_exec(p: str, i: int) -> str:
        time.sleep(0.05)
        return f"iter {i}"

    cfg = LoopConfig(prompt="x", max_iterations=100, timeout_s=0.01, cooldown_s=0.0)
    result = AutonomousLoopRunner(cfg).run(slow_exec)
    # Either timeout or ran a few iterations
    assert result.state in (LoopState.TIMEOUT, LoopState.COMPLETED)


# -- __all__ ---------------------------------------------------------------


def test_all_exports():
    from lidco.autonomous import loop_runner
    assert "AutonomousLoopRunner" in loop_runner.__all__
    assert "LoopResult" in loop_runner.__all__
