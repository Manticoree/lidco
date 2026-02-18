"""Tests for token budget tracking."""

from lidco.core.token_budget import TokenBudget


class TestTokenBudget:
    def test_record_and_total(self):
        budget = TokenBudget()
        budget.record(100, "coder")
        budget.record(50, "routing")
        assert budget.total_tokens == 150

    def test_by_role_tracking(self):
        budget = TokenBudget()
        budget.record(100, "coder")
        budget.record(200, "coder")
        budget.record(50, "routing")
        assert budget.by_role == {"coder": 300, "routing": 50}

    def test_remaining_unlimited(self):
        budget = TokenBudget(session_limit=0)
        budget.record(1000)
        assert budget.remaining is None
        assert budget.is_exhausted is False

    def test_remaining_with_limit(self):
        budget = TokenBudget(session_limit=1000)
        budget.record(300)
        assert budget.remaining == 700
        assert budget.is_exhausted is False

    def test_exhausted(self):
        budget = TokenBudget(session_limit=100)
        budget.record(150)
        assert budget.is_exhausted is True
        assert budget.remaining == 0

    def test_warning_callback_at_threshold(self):
        warnings: list[str] = []
        budget = TokenBudget(session_limit=100, warning_threshold=0.8)
        budget.set_warning_callback(lambda msg: warnings.append(msg))

        budget.record(50)  # 50% - no warning
        assert len(warnings) == 0

        budget.record(35)  # 85% - warning
        assert len(warnings) == 1
        assert "85%" in warnings[0]

    def test_warning_on_exhaustion(self):
        warnings: list[str] = []
        budget = TokenBudget(session_limit=100)
        budget.set_warning_callback(lambda msg: warnings.append(msg))

        budget.record(100)
        assert len(warnings) == 1
        assert "exhausted" in warnings[0].lower()

    def test_no_warning_when_unlimited(self):
        warnings: list[str] = []
        budget = TokenBudget(session_limit=0)
        budget.set_warning_callback(lambda msg: warnings.append(msg))

        budget.record(999999)
        assert len(warnings) == 0

    def test_summary(self):
        budget = TokenBudget(session_limit=1000)
        budget.record(200, "coder")
        budget.record(50, "routing")
        s = budget.summary()
        assert "250" in s
        assert "coder" in s
        assert "routing" in s

    def test_reset(self):
        budget = TokenBudget(session_limit=1000)
        budget.record(500, "coder", cost_usd=0.01)
        budget.reset()
        assert budget.total_tokens == 0
        assert budget.total_cost_usd == 0.0
        assert budget.by_role == {}
        assert budget.cost_by_role == {}
        assert budget.remaining == 1000


class TestTokenBudgetCost:
    def test_record_cost(self):
        budget = TokenBudget()
        budget.record(100, "coder", cost_usd=0.005)
        budget.record(50, "routing", cost_usd=0.001)
        assert budget.total_cost_usd == 0.006

    def test_cost_by_role(self):
        budget = TokenBudget()
        budget.record(100, "coder", cost_usd=0.005)
        budget.record(200, "coder", cost_usd=0.010)
        budget.record(50, "routing", cost_usd=0.001)
        assert budget.cost_by_role == {"coder": 0.015, "routing": 0.001}

    def test_cost_default_zero(self):
        budget = TokenBudget()
        budget.record(100, "coder")
        assert budget.total_cost_usd == 0.0
        assert budget.cost_by_role == {}

    def test_summary_includes_cost(self):
        budget = TokenBudget()
        budget.record(100, "coder", cost_usd=0.0032)
        s = budget.summary()
        assert "$0.0032" in s

    def test_summary_no_cost_when_zero(self):
        budget = TokenBudget()
        budget.record(100, "coder")
        s = budget.summary()
        assert "$" not in s
