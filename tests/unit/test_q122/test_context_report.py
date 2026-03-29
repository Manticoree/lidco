"""Tests for src/lidco/context/context_report.py."""
from lidco.context.token_estimator import TokenEstimator
from lidco.context.context_report import ContextReport, ContextUsage


def make_messages():
    return [
        {"role": "system", "content": "You are an assistant."},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I am doing well."},
        {"role": "user", "content": "What can you do?"},
    ]


class TestContextUsage:
    def test_fields(self):
        cu = ContextUsage(
            system_tokens=100,
            history_tokens=500,
            context_tokens=200,
            output_reserved=256,
            total=800,
            budget=4096,
        )
        assert cu.system_tokens == 100
        assert cu.history_tokens == 500
        assert cu.total == 800

    def test_utilization_with_budget(self):
        cu = ContextUsage(0, 0, 0, 0, total=1024, budget=4096)
        assert abs(cu.utilization - 0.25) < 0.01

    def test_utilization_no_budget(self):
        cu = ContextUsage(0, 0, 0, 0, total=100)
        assert cu.utilization == 0.0

    def test_utilization_full(self):
        cu = ContextUsage(0, 0, 0, 0, total=4096, budget=4096)
        assert abs(cu.utilization - 1.0) < 0.01

    def test_utilization_over_budget(self):
        cu = ContextUsage(0, 0, 0, 0, total=5000, budget=4096)
        assert cu.utilization > 1.0


class TestContextReport:
    def test_init(self):
        cr = ContextReport(budget=8192)
        assert cr._budget == 8192

    def test_init_custom_estimator(self):
        te = TokenEstimator(chars_per_token=3.0)
        cr = ContextReport(budget=4096, estimator=te)
        assert cr._estimator is te

    def test_measure_empty(self):
        cr = ContextReport(budget=4096)
        usage = cr.measure([])
        assert isinstance(usage, ContextUsage)
        assert usage.total == 0

    def test_measure_returns_context_usage(self):
        cr = ContextReport(budget=4096)
        msgs = make_messages()
        usage = cr.measure(msgs)
        assert isinstance(usage, ContextUsage)

    def test_measure_system_tokens(self):
        cr = ContextReport(budget=4096)
        msgs = [{"role": "system", "content": "You are an AI assistant."}]
        usage = cr.measure(msgs)
        assert usage.system_tokens > 0

    def test_measure_history_tokens(self):
        cr = ContextReport(budget=4096)
        msgs = [
            {"role": "user", "content": "Hello there."},
            {"role": "assistant", "content": "Hi!"},
        ]
        usage = cr.measure(msgs)
        assert usage.history_tokens > 0

    def test_measure_budget_preserved(self):
        cr = ContextReport(budget=4096)
        msgs = make_messages()
        usage = cr.measure(msgs)
        assert usage.budget == 4096

    def test_measure_output_reserved_positive(self):
        cr = ContextReport(budget=4096)
        usage = cr.measure([])
        assert usage.output_reserved > 0

    def test_format_returns_str(self):
        cr = ContextReport(budget=4096)
        msgs = make_messages()
        usage = cr.measure(msgs)
        result = cr.format(usage)
        assert isinstance(result, str)

    def test_format_contains_percentage(self):
        cr = ContextReport(budget=4096)
        msgs = make_messages()
        usage = cr.measure(msgs)
        result = cr.format(usage)
        assert "%" in result

    def test_format_contains_bar(self):
        cr = ContextReport(budget=4096)
        usage = ContextUsage(100, 200, 50, 256, 350, 4096)
        result = cr.format(usage)
        assert "[" in result and "]" in result

    def test_format_contains_token_counts(self):
        cr = ContextReport(budget=4096)
        usage = cr.measure(make_messages())
        result = cr.format(usage)
        assert "System" in result or "system" in result.lower()

    def test_is_critical_above_threshold(self):
        cr = ContextReport(budget=1000)
        usage = ContextUsage(0, 0, 0, 0, total=950, budget=1000)
        assert cr.is_critical(usage, threshold=0.9) is True

    def test_is_critical_below_threshold(self):
        cr = ContextReport(budget=1000)
        usage = ContextUsage(0, 0, 0, 0, total=500, budget=1000)
        assert cr.is_critical(usage, threshold=0.9) is False

    def test_is_critical_default_threshold(self):
        cr = ContextReport(budget=1000)
        usage = ContextUsage(0, 0, 0, 0, total=950, budget=1000)
        assert cr.is_critical(usage) is True

    def test_measure_total_is_sum(self):
        cr = ContextReport(budget=4096)
        msgs = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user message"},
        ]
        usage = cr.measure(msgs)
        assert usage.total == usage.system_tokens + usage.history_tokens + usage.context_tokens
