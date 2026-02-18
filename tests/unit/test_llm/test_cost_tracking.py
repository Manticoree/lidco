"""Tests for cost tracking in LLM responses and providers."""

from unittest.mock import patch

from lidco.agents.base import TokenUsage
from lidco.llm.base import LLMResponse
from lidco.llm.litellm_provider import calculate_cost


class TestLLMResponseCost:
    def test_default_cost_is_zero(self):
        resp = LLMResponse(content="hello", model="gpt-4o-mini")
        assert resp.cost_usd == 0.0

    def test_cost_usd_stored(self):
        resp = LLMResponse(content="hello", model="gpt-4o-mini", cost_usd=0.0042)
        assert resp.cost_usd == 0.0042

    def test_frozen_cost_field(self):
        resp = LLMResponse(content="hello", model="gpt-4o-mini", cost_usd=0.01)
        try:
            resp.cost_usd = 0.02  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except AttributeError:
            pass


class TestCalculateCost:
    def test_returns_cost_for_known_model(self):
        usage = {"prompt_tokens": 1000, "completion_tokens": 500}
        with patch("lidco.llm.litellm_provider.litellm.completion_cost", return_value=0.005):
            cost = calculate_cost("gpt-4o-mini", usage)
        assert cost == 0.005

    def test_returns_zero_on_exception(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 50}
        with patch(
            "lidco.llm.litellm_provider.litellm.completion_cost",
            side_effect=Exception("Unknown model"),
        ):
            cost = calculate_cost("unknown-model-xyz", usage)
        assert cost == 0.0

    def test_handles_empty_usage(self):
        with patch("lidco.llm.litellm_provider.litellm.completion_cost", return_value=0.0):
            cost = calculate_cost("gpt-4o-mini", {})
        assert cost == 0.0

    def test_handles_partial_usage(self):
        usage = {"prompt_tokens": 100}
        with patch("lidco.llm.litellm_provider.litellm.completion_cost", return_value=0.001):
            cost = calculate_cost("gpt-4o-mini", usage)
        assert cost == 0.001


class TestTokenUsageCost:
    def test_default_cost_zero(self):
        usage = TokenUsage()
        assert usage.total_cost_usd == 0.0

    def test_add_accumulates_cost(self):
        usage = TokenUsage()
        usage.add({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}, cost_usd=0.003)
        usage.add({"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}, cost_usd=0.007)
        assert usage.total_cost_usd == 0.01
        assert usage.total_tokens == 450

    def test_add_without_cost(self):
        usage = TokenUsage()
        usage.add({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        assert usage.total_cost_usd == 0.0
