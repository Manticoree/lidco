"""Tests for progress_tracker (task 1055)."""

import pytest
from lidco.autonomous.loop_config import IterationResult
from lidco.autonomous.progress_tracker import LoopProgressTracker


def _iter(i: int, output: str = "working", ms: int = 10, claimed: bool = False) -> IterationResult:
    return IterationResult(iteration=i, output=output, duration_ms=ms, claimed_complete=claimed)


# -- record / immutability ------------------------------------------------


def test_record_returns_new_tracker():
    t = LoopProgressTracker()
    t2 = t.record(_iter(1))
    assert t is not t2
    assert len(t.iterations) == 0
    assert len(t2.iterations) == 1


def test_record_chain():
    t = LoopProgressTracker()
    t = t.record(_iter(1)).record(_iter(2)).record(_iter(3))
    assert len(t.iterations) == 3


def test_iterations_is_tuple():
    t = LoopProgressTracker()
    assert isinstance(t.iterations, tuple)


def test_initial_iterations_empty():
    t = LoopProgressTracker()
    assert t.iterations == ()


# -- is_stuck -------------------------------------------------------------


def test_is_stuck_default_window():
    t = LoopProgressTracker()
    t = t.record(_iter(1, "same")).record(_iter(2, "same")).record(_iter(3, "same"))
    assert t.is_stuck() is True


def test_is_stuck_different_outputs():
    t = LoopProgressTracker()
    t = t.record(_iter(1, "a")).record(_iter(2, "b")).record(_iter(3, "c"))
    assert t.is_stuck() is False


def test_is_stuck_too_few_iterations():
    t = LoopProgressTracker()
    t = t.record(_iter(1, "same")).record(_iter(2, "same"))
    assert t.is_stuck() is False


def test_is_stuck_custom_window():
    t = LoopProgressTracker()
    t = t.record(_iter(1, "a")).record(_iter(2, "same")).record(_iter(3, "same"))
    assert t.is_stuck(window=2) is True


def test_is_stuck_empty_output_not_stuck():
    t = LoopProgressTracker()
    t = t.record(_iter(1, "")).record(_iter(2, "")).record(_iter(3, ""))
    assert t.is_stuck() is False


# -- progress_rate --------------------------------------------------------


def test_progress_rate_empty():
    t = LoopProgressTracker()
    assert t.progress_rate() == 0.0


def test_progress_rate_partial():
    t = LoopProgressTracker()
    t = t.record(_iter(1)).record(_iter(2)).record(_iter(3))
    rate = t.progress_rate()
    assert 0.0 < rate < 1.0


def test_progress_rate_complete():
    t = LoopProgressTracker()
    t = t.record(_iter(1)).record(_iter(2, claimed=True))
    assert t.progress_rate() == 1.0


def test_progress_rate_ten_iterations():
    t = LoopProgressTracker()
    for i in range(1, 11):
        t = t.record(_iter(i))
    assert t.progress_rate() == 1.0


# -- estimated_remaining --------------------------------------------------


def test_estimated_remaining_empty():
    t = LoopProgressTracker()
    assert t.estimated_remaining() == 10


def test_estimated_remaining_complete():
    t = LoopProgressTracker()
    t = t.record(_iter(1, claimed=True))
    assert t.estimated_remaining() == 0


def test_estimated_remaining_partial():
    t = LoopProgressTracker()
    t = t.record(_iter(1)).record(_iter(2)).record(_iter(3))
    remaining = t.estimated_remaining()
    assert remaining >= 0


# -- summary --------------------------------------------------------------


def test_summary_empty():
    t = LoopProgressTracker()
    s = t.summary()
    assert "No iterations" in s


def test_summary_with_data():
    t = LoopProgressTracker()
    t = t.record(_iter(1, ms=100)).record(_iter(2, ms=200))
    s = t.summary()
    assert "Iterations: 2" in s
    assert "Avg duration:" in s


def test_summary_shows_stuck_warning():
    t = LoopProgressTracker()
    t = t.record(_iter(1, "x")).record(_iter(2, "x")).record(_iter(3, "x"))
    s = t.summary()
    assert "stuck" in s.lower()


def test_summary_shows_progress():
    t = LoopProgressTracker()
    t = t.record(_iter(1))
    s = t.summary()
    assert "Progress:" in s


def test_summary_shows_remaining():
    t = LoopProgressTracker()
    t = t.record(_iter(1))
    s = t.summary()
    assert "Est. remaining:" in s


# -- __all__ ---------------------------------------------------------------


def test_all_exports():
    from lidco.autonomous import progress_tracker
    assert "LoopProgressTracker" in progress_tracker.__all__
