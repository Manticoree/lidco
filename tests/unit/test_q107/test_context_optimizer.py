"""Tests for src/lidco/context/optimizer.py."""
import pytest

from lidco.context.optimizer import (
    ContextEntry,
    ContextOptimizer,
    ContextSource,
    OptimizationResult,
)


class TestContextEntry:
    def test_token_count_positive(self):
        entry = ContextEntry(content="hello world")
        assert entry.token_count() >= 1

    def test_token_count_approximation(self):
        # ~4 chars per token
        entry = ContextEntry(content="a" * 400)
        assert entry.token_count() == 100

    def test_word_count(self):
        entry = ContextEntry(content="one two three")
        assert entry.word_count() == 3

    def test_default_source(self):
        entry = ContextEntry(content="x")
        assert entry.source == ContextSource.SNIPPET

    def test_default_priority(self):
        entry = ContextEntry(content="x")
        assert entry.priority == 1.0

    def test_label(self):
        entry = ContextEntry(content="x", label="main.py")
        assert entry.label == "main.py"


class TestContextOptimizer:
    def test_init_default_budget(self):
        opt = ContextOptimizer()
        assert opt.token_budget == ContextOptimizer.DEFAULT_BUDGET

    def test_init_custom_budget(self):
        opt = ContextOptimizer(token_budget=512)
        assert opt.token_budget == 512

    def test_init_invalid_budget(self):
        with pytest.raises(ValueError):
            ContextOptimizer(token_budget=0)

    def test_add_entry(self):
        opt = ContextOptimizer()
        opt.add(ContextEntry(content="hello"))
        assert len(opt.entries) == 1

    def test_add_text(self):
        opt = ContextOptimizer()
        entry = opt.add_text("hello", label="greet")
        assert entry.label == "greet"
        assert len(opt.entries) == 1

    def test_remove_by_label(self):
        opt = ContextOptimizer()
        opt.add_text("x", label="keep")
        opt.add_text("y", label="remove")
        removed = opt.remove("remove")
        assert removed == 1
        assert all(e.label != "remove" for e in opt.entries)

    def test_remove_nonexistent(self):
        opt = ContextOptimizer()
        assert opt.remove("ghost") == 0

    def test_clear(self):
        opt = ContextOptimizer()
        opt.add_text("a")
        opt.add_text("b")
        opt.clear()
        assert len(opt.entries) == 0

    def test_total_tokens(self):
        opt = ContextOptimizer()
        opt.add(ContextEntry(content="a" * 40))   # 10 tokens
        opt.add(ContextEntry(content="b" * 40))   # 10 tokens
        assert opt.total_tokens() == 20

    def test_optimize_all_fit(self):
        opt = ContextOptimizer(token_budget=1000)
        opt.add_text("short", label="a", priority=1.0)
        opt.add_text("also short", label="b", priority=2.0)
        result = opt.optimize()
        assert len(result.included) == 2
        assert len(result.excluded) == 0

    def test_optimize_budget_exceeded_excludes_lowest(self):
        opt = ContextOptimizer(token_budget=10)
        opt.add(ContextEntry(content="a" * 40, priority=2.0, label="high"))   # 10 tok
        opt.add(ContextEntry(content="b" * 40, priority=1.0, label="low"))    # 10 tok
        result = opt.optimize()
        included_labels = [e.label for e in result.included]
        assert "high" in included_labels
        assert "low" not in included_labels

    def test_optimize_pinned_always_first(self):
        opt = ContextOptimizer(token_budget=20)
        opt.add(ContextEntry(content="a" * 40, priority=10.0, label="pinned"))  # 10 tok
        opt.add(ContextEntry(content="b" * 8, priority=1.0, label="normal"))    # 2 tok
        result = opt.optimize()
        included_labels = [e.label for e in result.included]
        assert "pinned" in included_labels

    def test_optimization_result_utilization(self):
        opt = ContextOptimizer(token_budget=100)
        opt.add(ContextEntry(content="a" * 40))  # 10 tokens
        result = opt.optimize()
        assert 0.0 <= result.utilization <= 1.0

    def test_optimization_result_prompt_text(self):
        opt = ContextOptimizer(token_budget=1000)
        opt.add_text("line1", label="f1")
        opt.add_text("line2", label="f2")
        result = opt.optimize()
        text = result.prompt_text()
        assert "line1" in text
        assert "line2" in text

    def test_prompt_text_includes_labels(self):
        opt = ContextOptimizer(token_budget=1000)
        opt.add_text("content", label="src/main.py")
        result = opt.optimize()
        assert "src/main.py" in result.prompt_text()

    def test_set_budget(self):
        opt = ContextOptimizer(token_budget=100)
        opt.set_budget(200)
        assert opt.token_budget == 200

    def test_set_budget_invalid(self):
        opt = ContextOptimizer()
        with pytest.raises(ValueError):
            opt.set_budget(0)

    def test_score_file_relevance_exact_match(self):
        score = ContextOptimizer.score_file_relevance("src/auth/login.py", "login")
        assert score > 0.5

    def test_score_file_relevance_no_match(self):
        score = ContextOptimizer.score_file_relevance("utils/math.py", "authentication")
        assert score == 0.0

    def test_score_file_relevance_empty_query(self):
        score = ContextOptimizer.score_file_relevance("any/file.py", "")
        assert score == 0.5

    def test_stats_keys(self):
        opt = ContextOptimizer(token_budget=1000)
        opt.add_text("hello")
        s = opt.stats()
        assert "entries" in s
        assert "total_tokens" in s
        assert "budget" in s
        assert "included" in s
        assert "excluded" in s
        assert "utilization" in s
