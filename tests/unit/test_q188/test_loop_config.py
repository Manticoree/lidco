"""Tests for loop_config (task 1052)."""

import pytest
from lidco.autonomous.loop_config import IterationResult, LoopConfig, LoopState


# -- LoopConfig -----------------------------------------------------------


def test_loop_config_defaults():
    cfg = LoopConfig(prompt="do stuff")
    assert cfg.prompt == "do stuff"
    assert cfg.max_iterations == 10
    assert cfg.completion_promise is None
    assert cfg.timeout_s is None
    assert cfg.cooldown_s == 1.0
    assert cfg.allow_early_exit is False


def test_loop_config_custom_values():
    cfg = LoopConfig(
        prompt="fix it",
        max_iterations=5,
        completion_promise="ALL TESTS PASS",
        timeout_s=30.0,
        cooldown_s=0.5,
        allow_early_exit=True,
    )
    assert cfg.max_iterations == 5
    assert cfg.completion_promise == "ALL TESTS PASS"
    assert cfg.timeout_s == 30.0
    assert cfg.cooldown_s == 0.5
    assert cfg.allow_early_exit is True


def test_loop_config_is_frozen():
    cfg = LoopConfig(prompt="test")
    with pytest.raises(AttributeError):
        cfg.prompt = "other"  # type: ignore[misc]


def test_loop_config_equality():
    a = LoopConfig(prompt="x", max_iterations=3)
    b = LoopConfig(prompt="x", max_iterations=3)
    assert a == b


def test_loop_config_inequality():
    a = LoopConfig(prompt="x")
    b = LoopConfig(prompt="y")
    assert a != b


# -- LoopState ------------------------------------------------------------


def test_loop_state_values():
    assert LoopState.IDLE == "idle"
    assert LoopState.RUNNING == "running"
    assert LoopState.PAUSED == "paused"
    assert LoopState.COMPLETED == "completed"
    assert LoopState.FAILED == "failed"
    assert LoopState.TIMEOUT == "timeout"


def test_loop_state_from_string():
    assert LoopState("running") == LoopState.RUNNING


def test_loop_state_all_members():
    assert len(LoopState) == 6


# -- IterationResult ------------------------------------------------------


def test_iteration_result_creation():
    r = IterationResult(iteration=1, output="hello", duration_ms=50, claimed_complete=False)
    assert r.iteration == 1
    assert r.output == "hello"
    assert r.duration_ms == 50
    assert r.claimed_complete is False


def test_iteration_result_frozen():
    r = IterationResult(iteration=1, output="x", duration_ms=10, claimed_complete=True)
    with pytest.raises(AttributeError):
        r.output = "changed"  # type: ignore[misc]


def test_iteration_result_equality():
    a = IterationResult(iteration=1, output="x", duration_ms=10, claimed_complete=False)
    b = IterationResult(iteration=1, output="x", duration_ms=10, claimed_complete=False)
    assert a == b


def test_iteration_result_claimed_complete_true():
    r = IterationResult(iteration=3, output="done", duration_ms=5, claimed_complete=True)
    assert r.claimed_complete is True


def test_iteration_result_hash_works():
    r = IterationResult(iteration=1, output="x", duration_ms=10, claimed_complete=False)
    s = {r}
    assert r in s


# -- __all__ ---------------------------------------------------------------


def test_all_exports():
    from lidco.autonomous import loop_config
    assert "LoopConfig" in loop_config.__all__
    assert "LoopState" in loop_config.__all__
    assert "IterationResult" in loop_config.__all__
