"""Tests for ModelOptimizer."""

from lidco.economics.model_optimizer import (
    ModelOptimizer,
    ModelRecommendation,
    ModelTier,
    QualityRecord,
    TaskClassification,
)


class TestModelOptimizer:
    def _make_tiers(self):
        cheap = ModelTier(name="haiku", cost_per_1k_input=0.25, cost_per_1k_output=1.25, quality_score=0.7)
        mid = ModelTier(name="sonnet", cost_per_1k_input=3.0, cost_per_1k_output=15.0, quality_score=0.9)
        expensive = ModelTier(name="opus", cost_per_1k_input=15.0, cost_per_1k_output=75.0, quality_score=1.0)
        return cheap, mid, expensive

    def test_add_and_remove_tier(self):
        opt = ModelOptimizer()
        cheap, mid, _ = self._make_tiers()
        opt.add_tier(cheap)
        opt.add_tier(mid)
        assert len(opt.list_tiers()) == 2
        assert opt.remove_tier("haiku") is True
        assert opt.remove_tier("nonexistent") is False
        assert len(opt.list_tiers()) == 1

    def test_get_tier(self):
        opt = ModelOptimizer()
        cheap, _, _ = self._make_tiers()
        opt.add_tier(cheap)
        assert opt.get_tier("haiku") is not None
        assert opt.get_tier("nope") is None

    def test_list_tiers_sorted_by_cost(self):
        cheap, mid, expensive = self._make_tiers()
        opt = ModelOptimizer(tiers=[expensive, cheap, mid])
        tiers = opt.list_tiers()
        assert tiers[0].name == "haiku"
        assert tiers[1].name == "sonnet"
        assert tiers[2].name == "opus"

    def test_classify_simple_task(self):
        opt = ModelOptimizer()
        result = opt.classify_task("summarize this list")
        assert result.complexity == "simple"
        assert result.confidence > 0.5

    def test_classify_complex_task(self):
        opt = ModelOptimizer()
        result = opt.classify_task("architect a new security review system")
        assert result.complexity == "complex"
        assert result.confidence > 0.5

    def test_classify_moderate_task(self):
        opt = ModelOptimizer()
        result = opt.classify_task("hello world")
        assert result.complexity == "moderate"
        assert result.confidence == 0.5

    def test_recommend_model_downgrades_for_simple(self):
        cheap, mid, expensive = self._make_tiers()
        opt = ModelOptimizer(tiers=[cheap, mid, expensive])
        rec = opt.recommend_model("summarize this list", "opus")
        assert rec.recommended_model == "haiku"
        assert rec.estimated_savings_pct > 0
        assert rec.task_complexity == "simple"

    def test_recommend_model_keeps_for_complex(self):
        cheap, mid, expensive = self._make_tiers()
        opt = ModelOptimizer(tiers=[cheap, mid, expensive])
        rec = opt.recommend_model("architect a new security review", "opus")
        assert rec.recommended_model == "opus"
        assert rec.estimated_savings_pct == 0.0

    def test_recommend_model_no_tiers_fallback(self):
        opt = ModelOptimizer()
        rec = opt.recommend_model("summarize this", "gpt-4")
        assert rec.recommended_model == "gpt-4"
        assert rec.reason == "No tier data available; keeping current model."

    def test_record_and_get_quality(self):
        opt = ModelOptimizer()
        opt.record_quality("haiku", "simple", True, cost=0.01, tokens=100)
        opt.record_quality("haiku", "simple", True, cost=0.01, tokens=100)
        opt.record_quality("haiku", "simple", False, cost=0.01, tokens=100)
        qr = opt.get_quality("haiku", "simple")
        assert qr is not None
        assert qr.successes == 2
        assert qr.failures == 1
        assert abs(qr.success_rate - 2 / 3) < 0.01

    def test_get_quality_nonexistent(self):
        opt = ModelOptimizer()
        assert opt.get_quality("nope", "nope") is None

    def test_summary(self):
        cheap, _, _ = self._make_tiers()
        opt = ModelOptimizer(tiers=[cheap])
        opt.record_quality("haiku", "simple", True)
        s = opt.summary()
        assert "haiku" in s
        assert "Model tiers: 1" in s
