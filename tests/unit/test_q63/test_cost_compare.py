"""Tests for ModelComparator and cost table — Q63 Task 426."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestCostTable:
    def test_gpt4o_has_costs(self):
        from lidco.ai.cost_compare import _DEFAULT_COST_PER_TOKEN
        assert "gpt-4o" in _DEFAULT_COST_PER_TOKEN
        assert "input" in _DEFAULT_COST_PER_TOKEN["gpt-4o"]
        assert "output" in _DEFAULT_COST_PER_TOKEN["gpt-4o"]

    def test_claude_sonnet_has_costs(self):
        from lidco.ai.cost_compare import _DEFAULT_COST_PER_TOKEN
        # check at least one claude model
        claude_keys = [k for k in _DEFAULT_COST_PER_TOKEN if "claude" in k]
        assert len(claude_keys) > 0

    def test_lookup_cost_known_model(self):
        from lidco.ai.cost_compare import _lookup_cost
        cost = _lookup_cost("gpt-4o", 1000, 500)
        assert cost > 0.0

    def test_lookup_cost_unknown_model_has_fallback(self):
        from lidco.ai.cost_compare import _lookup_cost
        cost = _lookup_cost("unknown-model-xyz", 1000, 500)
        assert cost >= 0.0


class TestComparisonResult:
    def test_success_property(self):
        from lidco.ai.cost_compare import ComparisonResult
        r = ComparisonResult(model="gpt-4o", response="hello")
        assert r.success is True

    def test_failure_property(self):
        from lidco.ai.cost_compare import ComparisonResult
        r = ComparisonResult(model="gpt-4o", response="", error="timeout")
        assert r.success is False

    def test_quality_chars(self):
        from lidco.ai.cost_compare import ComparisonResult
        r = ComparisonResult(model="gpt-4o", response="hello world")
        assert r.quality_chars == 11


class TestModelComparator:
    def test_empty_models_returns_empty(self):
        from lidco.ai.cost_compare import ModelComparator
        session = MagicMock()
        comp = ModelComparator(session=session)
        import asyncio
        result = asyncio.run(comp.compare("hello", []))
        assert result == []

    @pytest.mark.asyncio
    async def test_compare_returns_one_per_model(self):
        from lidco.ai.cost_compare import ModelComparator
        session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "response text"
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 20
        session.llm.complete = AsyncMock(return_value=mock_resp)
        comp = ModelComparator(session=session)
        results = await comp.compare("test", ["gpt-4o", "gpt-4o-mini"])
        assert len(results) == 2

    def test_format_table_returns_string(self):
        from lidco.ai.cost_compare import ModelComparator, ComparisonResult
        session = MagicMock()
        comp = ModelComparator(session=session)
        results = [
            ComparisonResult(model="gpt-4o", response="r1", tokens_in=100, tokens_out=50, cost_usd=0.001, duration_ms=200.0),
        ]
        table = comp.format_table(results)
        assert "gpt-4o" in table
