"""Tests for CostProjector — Task 586."""

import json
import tempfile
from pathlib import Path

import pytest

from lidco.ai.cost_projector import (
    CostProjection,
    CostProjector,
    ModelPricing,
    StepEstimate,
)


# ---------------------------------------------------------------------------
# StepEstimate / basic estimation
# ---------------------------------------------------------------------------


def test_estimate_step_returns_estimate():
    proj = CostProjector(model="gpt-4o")
    est = proj.estimate_step("analyze the codebase", context_files=3)
    assert isinstance(est, StepEstimate)
    assert est.estimated_input_tokens > 0
    assert est.estimated_output_tokens > 0
    assert est.estimated_cost_usd > 0
    assert est.estimated_seconds > 0
    assert 0.0 <= est.confidence <= 1.0


def test_estimate_step_more_context_more_tokens():
    proj = CostProjector(model="gpt-4o")
    est_few = proj.estimate_step("fix bug", context_files=1)
    est_many = proj.estimate_step("fix bug", context_files=10)
    assert est_many.estimated_input_tokens > est_few.estimated_input_tokens


def test_estimate_step_output_lines_increase_output_tokens():
    proj = CostProjector(model="gpt-4o")
    est_small = proj.estimate_step("write code", expected_output_lines=5)
    est_large = proj.estimate_step("write code", expected_output_lines=100)
    assert est_large.estimated_output_tokens > est_small.estimated_output_tokens


def test_estimate_step_description_words_affect_input():
    proj = CostProjector(model="gpt-4o")
    est_short = proj.estimate_step("fix")
    est_long = proj.estimate_step("fix the authentication bug in the login handler module")
    assert est_long.estimated_input_tokens > est_short.estimated_input_tokens


def test_estimate_step_default_confidence_is_low():
    """Without history, confidence should be the heuristic default (0.3)."""
    proj = CostProjector(model="gpt-4o")
    est = proj.estimate_step("something new")
    assert est.confidence == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Plan estimation
# ---------------------------------------------------------------------------


def test_estimate_plan():
    proj = CostProjector(model="gpt-4o")
    steps = [
        {"name": "analyze", "context_files": 2},
        {"name": "implement", "context_files": 5, "output_lines": 100},
        {"name": "test", "context_files": 3},
    ]
    projection = proj.estimate_plan(steps)
    assert isinstance(projection, CostProjection)
    assert projection.total_cost_usd > 0
    assert projection.total_input_tokens > 0
    assert projection.total_output_tokens > 0
    assert projection.total_seconds > 0
    assert len(projection.steps) == 3
    assert projection.model == "gpt-4o"


def test_estimate_plan_totals_match_steps():
    proj = CostProjector(model="gpt-4o")
    steps = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
    projection = proj.estimate_plan(steps)
    sum_input = sum(s.estimated_input_tokens for s in projection.steps)
    sum_output = sum(s.estimated_output_tokens for s in projection.steps)
    sum_cost = sum(s.estimated_cost_usd for s in projection.steps)
    sum_time = sum(s.estimated_seconds for s in projection.steps)
    assert projection.total_input_tokens == sum_input
    assert projection.total_output_tokens == sum_output
    assert projection.total_cost_usd == pytest.approx(sum_cost, rel=1e-9)
    assert projection.total_seconds == pytest.approx(sum_time, rel=1e-9)


def test_estimate_plan_empty():
    proj = CostProjector(model="gpt-4o")
    projection = proj.estimate_plan([])
    assert projection.total_cost_usd == 0.0
    assert projection.total_input_tokens == 0
    assert len(projection.steps) == 0


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def test_format_summary_contains_dollar():
    proj = CostProjector(model="gpt-4o")
    steps = [{"name": "do stuff"}]
    projection = proj.estimate_plan(steps)
    summary = projection.format_summary()
    assert "$" in summary


def test_format_summary_confidence_label():
    proj = CostProjector(model="gpt-4o")
    steps = [{"name": "step1"}]
    projection = proj.estimate_plan(steps)
    summary = projection.format_summary()
    assert any(label in summary for label in ["low", "medium", "high"])


def test_format_summary_confidence_low():
    """All-heuristic steps should produce 'low' label."""
    proj = CostProjector(model="gpt-4o")
    projection = proj.estimate_plan([{"name": "x"}])
    assert "low" in projection.format_summary()


def test_format_detailed_has_totals():
    proj = CostProjector(model="gpt-4o")
    steps = [{"name": "a"}, {"name": "b"}]
    projection = proj.estimate_plan(steps)
    detailed = projection.format_detailed()
    assert "TOTAL" in detailed.upper()


def test_format_detailed_has_step_names():
    proj = CostProjector(model="gpt-4o")
    steps = [{"name": "analyze"}, {"name": "implement"}]
    projection = proj.estimate_plan(steps)
    detailed = projection.format_detailed()
    assert "analyze" in detailed
    assert "implement" in detailed


# ---------------------------------------------------------------------------
# History: record + reload
# ---------------------------------------------------------------------------


def test_record_actual_and_load(tmp_path):
    history_file = tmp_path / "history.json"
    proj = CostProjector(model="gpt-4o", history_path=history_file)
    proj.record_actual("analyze", input_tokens=1000, output_tokens=200, elapsed=5.0)
    # Load fresh instance
    proj2 = CostProjector(model="gpt-4o", history_path=history_file)
    assert "analyze" in proj2._history


def test_record_actual_keeps_max_10(tmp_path):
    history_file = tmp_path / "history.json"
    proj = CostProjector(model="gpt-4o", history_path=history_file)
    for i in range(15):
        proj.record_actual("step", input_tokens=100 + i, output_tokens=50, elapsed=1.0)
    assert len(proj._history["step"]["samples"]) == 10


def test_history_confidence_higher():
    """After recording actual data, estimate confidence should be higher."""
    with tempfile.TemporaryDirectory() as d:
        hp = Path(d) / "h.json"
        proj = CostProjector(model="gpt-4o", history_path=hp)
        proj.record_actual("analyze code", 1000, 200, 5.0)
        proj.record_actual("analyze code", 1100, 180, 4.8)
        est = proj.estimate_step("analyze code")
        assert est.confidence > 0.5


def test_history_uses_actual_averages():
    """After recording, estimates should use historical averages."""
    with tempfile.TemporaryDirectory() as d:
        hp = Path(d) / "h.json"
        proj = CostProjector(model="gpt-4o", history_path=hp)
        proj.record_actual("my step", 2000, 500, 10.0)
        proj.record_actual("my step", 2200, 600, 12.0)
        est = proj.estimate_step("my step")
        # Should be close to average of actuals
        assert abs(est.estimated_input_tokens - 2100) < 200
        assert abs(est.estimated_output_tokens - 550) < 100


def test_no_history_path_means_no_persistence():
    proj = CostProjector(model="gpt-4o", history_path=None)
    proj.record_actual("step", 100, 50, 1.0)
    assert "step" in proj._history  # in-memory still works
    # But nothing written to disk — no error raised


# ---------------------------------------------------------------------------
# Accuracy report
# ---------------------------------------------------------------------------


def test_accuracy_report_no_history():
    proj = CostProjector(model="gpt-4o")
    report = proj.accuracy_report()
    assert "No historical" in report


def test_accuracy_report_with_history(tmp_path):
    hp = tmp_path / "h.json"
    proj = CostProjector(model="gpt-4o", history_path=hp)
    proj.record_actual("task", 1000, 300, 5.0)
    report = proj.accuracy_report()
    assert len(report) > 0
    assert "task" in report


# ---------------------------------------------------------------------------
# Pricing: fallback and custom
# ---------------------------------------------------------------------------


def test_fallback_pricing():
    """Unknown model falls back to gpt-4o pricing."""
    proj = CostProjector(model="unknown-model-xyz")
    est = proj.estimate_step("do something")
    assert est.estimated_cost_usd > 0


def test_custom_pricing():
    custom = {"my-model": ModelPricing("my-model", 0.001, 0.002, 80.0)}
    proj = CostProjector(model="my-model", pricing=custom)
    est = proj.estimate_step("task", context_files=2)
    assert est.estimated_cost_usd > 0


def test_prefix_matching_pricing():
    """'claude-sonnet' should match 'claude-sonnet-4' in default pricing."""
    proj = CostProjector(model="claude-sonnet")
    pricing = proj._get_pricing()
    assert pricing.model == "claude-sonnet-4"


def test_exact_match_pricing():
    proj = CostProjector(model="gpt-4o-mini")
    pricing = proj._get_pricing()
    assert pricing.model == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Load history edge cases
# ---------------------------------------------------------------------------


def test_load_history_missing_file(tmp_path):
    hp = tmp_path / "nonexistent.json"
    proj = CostProjector(model="gpt-4o", history_path=hp)
    assert proj._history == {}


def test_load_history_corrupt_json(tmp_path):
    hp = tmp_path / "bad.json"
    hp.write_text("not valid json {{{")
    proj = CostProjector(model="gpt-4o", history_path=hp)
    assert proj._history == {}
