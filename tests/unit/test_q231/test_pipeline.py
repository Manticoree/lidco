"""Tests for lidco.budget.pipeline."""
from __future__ import annotations

import pytest

from lidco.budget.pipeline import BudgetPipeline, PipelineResult, PipelineStage


class TestPipelineStage:
    def test_values(self) -> None:
        assert PipelineStage.ESTIMATE == "estimate"
        assert PipelineStage.CHECK == "check"
        assert PipelineStage.EXECUTE == "execute"
        assert PipelineStage.RECORD == "record"
        assert PipelineStage.COMPACT == "compact"


class TestPipelineResult:
    def test_frozen(self) -> None:
        r = PipelineResult(stage=PipelineStage.ESTIMATE)
        with pytest.raises(AttributeError):
            r.passed = False  # type: ignore[misc]

    def test_defaults(self) -> None:
        r = PipelineResult(stage=PipelineStage.CHECK)
        assert r.passed is True
        assert r.message == ""
        assert r.tokens == 0


class TestBudgetPipeline:
    def test_init_defaults(self) -> None:
        p = BudgetPipeline()
        assert p.remaining() == 128_000

    def test_estimate_returns_result(self) -> None:
        p = BudgetPipeline()
        r = p.estimate("read", "x" * 100)
        assert r.stage == PipelineStage.ESTIMATE
        assert r.tokens == 25  # 100 // 4

    def test_check_passes_within_budget(self) -> None:
        p = BudgetPipeline(budget_limit=1000)
        r = p.check(500)
        assert r.passed is True

    def test_check_fails_over_budget(self) -> None:
        p = BudgetPipeline(budget_limit=100)
        r = p.check(200)
        assert r.passed is False
        assert "Over budget" in r.message

    def test_execute_gate_follows_check(self) -> None:
        p = BudgetPipeline(budget_limit=100)
        p.check(200)
        gate = p.execute_gate()
        assert gate.passed is False
        assert gate.stage == PipelineStage.EXECUTE

    def test_record_subtracts_tokens(self) -> None:
        p = BudgetPipeline(budget_limit=1000)
        p.record(300)
        assert p.remaining() == 700

    def test_compact_check_no_compaction(self) -> None:
        p = BudgetPipeline()
        r = p.compact_check(0.5)
        assert r.passed is True

    def test_compact_check_needs_compaction(self) -> None:
        p = BudgetPipeline()
        r = p.compact_check(0.90)
        assert r.passed is False
        assert "recommended" in r.message.lower()

    def test_run_all_stages(self) -> None:
        p = BudgetPipeline(budget_limit=10_000)
        results = p.run("edit", "x" * 40, actual_tokens=20)
        assert len(results) == 5
        stages = [r.stage for r in results]
        assert PipelineStage.ESTIMATE in stages
        assert PipelineStage.CHECK in stages
        assert PipelineStage.EXECUTE in stages
        assert PipelineStage.RECORD in stages
        assert PipelineStage.COMPACT in stages

    def test_summary_returns_string(self) -> None:
        p = BudgetPipeline(budget_limit=5000)
        p.run("read", "hello")
        s = p.summary()
        assert "Pipeline" in s
        assert "5,000" in s
