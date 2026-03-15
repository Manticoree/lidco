"""Tests for TaskComplexityAnalyzer and AdaptiveBudget — Q63 Task 424."""

from __future__ import annotations

import pytest


class TestTaskComplexityAnalyzer:
    def test_empty_prompt_zero_score(self):
        from lidco.ai.adaptive_budget import TaskComplexityAnalyzer
        analyzer = TaskComplexityAnalyzer()
        score = analyzer.score("")
        assert score.value == 0.0

    def test_short_prompt_simple_bucket(self):
        from lidco.ai.adaptive_budget import TaskComplexityAnalyzer
        analyzer = TaskComplexityAnalyzer()
        score = analyzer.score("hi")
        assert score.bucket == "simple"

    def test_long_prompt_increases_score(self):
        from lidco.ai.adaptive_budget import TaskComplexityAnalyzer
        analyzer = TaskComplexityAnalyzer()
        long = "word " * 500
        score = analyzer.score(long)
        assert score.value > 0.0

    def test_code_block_detected(self):
        from lidco.ai.adaptive_budget import TaskComplexityAnalyzer
        analyzer = TaskComplexityAnalyzer()
        score = analyzer.score("review this:\n```python\ndef foo(): pass\n```")
        assert score.has_code

    def test_file_references_detected(self):
        from lidco.ai.adaptive_budget import TaskComplexityAnalyzer
        analyzer = TaskComplexityAnalyzer()
        score = analyzer.score("look at src/foo.py and tests/bar.py")
        assert score.has_files

    def test_multi_step_detected(self):
        from lidco.ai.adaptive_budget import TaskComplexityAnalyzer
        analyzer = TaskComplexityAnalyzer()
        score = analyzer.score("first do this, then do that, finally clean up")
        assert score.multi_step

    def test_value_capped_at_one(self):
        from lidco.ai.adaptive_budget import TaskComplexityAnalyzer
        analyzer = TaskComplexityAnalyzer()
        extreme = "design ```python\n" + "x = 1\n" * 200 + "```\nsrc/a.py src/b.py first then"
        score = analyzer.score(extreme)
        assert score.value <= 1.0


class TestAdaptiveBudget:
    def test_compute_returns_positive_int(self):
        from lidco.ai.adaptive_budget import AdaptiveBudget
        budget = AdaptiveBudget()
        result = budget.compute("simple question")
        assert isinstance(result, int)
        assert result > 0

    def test_deeper_history_increases_budget(self):
        from lidco.ai.adaptive_budget import AdaptiveBudget
        budget = AdaptiveBudget()
        b0 = budget.compute("complex design architecture refactor", history_length=0)
        b20 = budget.compute("complex design architecture refactor", history_length=20)
        assert b20 >= b0

    def test_record_usage_tracked(self):
        from lidco.ai.adaptive_budget import AdaptiveBudget
        budget = AdaptiveBudget()
        budget.record_usage(100, 200)
        assert budget.call_count == 1

    def test_efficiency_ratio_zero_before_usage(self):
        from lidco.ai.adaptive_budget import AdaptiveBudget
        budget = AdaptiveBudget()
        assert budget.efficiency_ratio == 0.0
