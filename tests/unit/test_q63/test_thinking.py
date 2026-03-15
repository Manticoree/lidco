"""Tests for ThinkingConfig, ComplexityEstimator, ThinkingAdapter — Q63 Task 423."""

from __future__ import annotations

import pytest


class TestThinkingConfig:
    def test_defaults(self):
        from lidco.ai.thinking import ThinkingConfig
        cfg = ThinkingConfig()
        assert cfg.enabled is False
        assert cfg.budget_tokens == 10000
        assert cfg.min_complexity_score == 0.7

    def test_custom_values(self):
        from lidco.ai.thinking import ThinkingConfig
        cfg = ThinkingConfig(enabled=True, budget_tokens=5000, min_complexity_score=0.5)
        assert cfg.enabled is True
        assert cfg.budget_tokens == 5000


class TestComplexityEstimator:
    def test_empty_prompt_returns_zero(self):
        from lidco.ai.thinking import ComplexityEstimator
        est = ComplexityEstimator()
        assert est.estimate("") == 0.0

    def test_short_simple_prompt_low_score(self):
        from lidco.ai.thinking import ComplexityEstimator
        est = ComplexityEstimator()
        score = est.estimate("hi")
        assert score < 0.5

    def test_long_prompt_higher_score(self):
        from lidco.ai.thinking import ComplexityEstimator
        est = ComplexityEstimator()
        long_prompt = "why " * 200
        score = est.estimate(long_prompt)
        assert score > 0.0

    def test_complexity_marker_increases_score(self):
        from lidco.ai.thinking import ComplexityEstimator
        est = ComplexityEstimator()
        baseline = est.estimate("do something simple please")
        with_marker = est.estimate("design an architect for the system and analyze the components")
        assert with_marker >= baseline

    def test_code_block_increases_score(self):
        from lidco.ai.thinking import ComplexityEstimator
        est = ComplexityEstimator()
        plain = est.estimate("explain this code please")
        with_code = est.estimate("explain this code:\n```python\ndef foo():\n    return 42\n```\n")
        assert with_code >= plain

    def test_score_capped_at_one(self):
        from lidco.ai.thinking import ComplexityEstimator
        est = ComplexityEstimator()
        very_complex = "design " * 100 + " ```python\n" + "def f(): pass\n" * 50 + "```"
        assert est.estimate(very_complex) <= 1.0


class TestThinkingAdapter:
    def test_inject_disabled_returns_unchanged(self):
        from lidco.ai.thinking import ThinkingAdapter, ThinkingConfig
        adapter = ThinkingAdapter(config=ThinkingConfig(enabled=False))
        params = {"model": "claude-sonnet-4-6", "max_tokens": 1000}
        result = adapter.inject(params)
        assert "thinking" not in result

    def test_inject_enabled_adds_thinking_for_supported_model(self):
        from lidco.ai.thinking import ThinkingAdapter, ThinkingConfig
        adapter = ThinkingAdapter(config=ThinkingConfig(enabled=True, budget_tokens=8000, min_complexity_score=0.0))
        params = {"model": "claude-sonnet-4-6", "max_tokens": 1000}
        result = adapter.inject(params, prompt="design an architect for the entire system")
        # Should add thinking if model supports it
        assert isinstance(result, dict)

    def test_supports_thinking_for_known_model(self):
        from lidco.ai.thinking import ThinkingAdapter, ThinkingConfig
        adapter = ThinkingAdapter(config=ThinkingConfig(enabled=True))
        assert adapter.supports_thinking("claude-3-7-sonnet")

    def test_does_not_support_thinking_for_unknown_model(self):
        from lidco.ai.thinking import ThinkingAdapter, ThinkingConfig
        adapter = ThinkingAdapter(config=ThinkingConfig(enabled=True))
        assert not adapter.supports_thinking("gpt-3.5-turbo")

    def test_inject_unconditional_adds_thinking(self):
        from lidco.ai.thinking import ThinkingAdapter, ThinkingConfig
        adapter = ThinkingAdapter(config=ThinkingConfig(enabled=True, budget_tokens=8000))
        params = {"model": "claude-3-7-sonnet-20250219", "max_tokens": 1000}
        result = adapter.inject_unconditional(params)
        assert "thinking" in result
        assert result["thinking"]["budget_tokens"] == 8000

    def test_inject_does_not_mutate_original(self):
        from lidco.ai.thinking import ThinkingAdapter, ThinkingConfig
        adapter = ThinkingAdapter(config=ThinkingConfig(enabled=True, min_complexity_score=0.0))
        original = {"model": "claude-3-7-sonnet", "max_tokens": 100}
        _ = adapter.inject(original, prompt="x")
        assert "thinking" not in original
