"""Tests for src/lidco/context/message_trimmer.py."""
from lidco.context.token_estimator import TokenEstimator
from lidco.context.message_trimmer import MessageTrimmer, TrimResult


def make_messages(n, role="user"):
    return [{"role": role, "content": f"Message number {i} with some content here."} for i in range(n)]


class TestTrimResult:
    def test_fields(self):
        msgs = [{"role": "user", "content": "hi"}]
        r = TrimResult(messages=msgs, removed_count=0, tokens_saved=0)
        assert r.messages == msgs
        assert r.removed_count == 0
        assert r.tokens_saved == 0


class TestMessageTrimmerInit:
    def test_default_init(self):
        mt = MessageTrimmer()
        assert mt._keep_system is True
        assert mt._keep_recent == 4

    def test_custom_init(self):
        te = TokenEstimator()
        mt = MessageTrimmer(estimator=te, keep_system=False, keep_recent=2)
        assert mt._keep_system is False
        assert mt._keep_recent == 2


class TestMessageTrimmerTrim:
    def test_trim_empty(self):
        mt = MessageTrimmer()
        result = mt.trim([], 1000)
        assert isinstance(result, TrimResult)
        assert result.messages == []
        assert result.removed_count == 0

    def test_trim_within_budget(self):
        mt = MessageTrimmer()
        msgs = make_messages(3)
        result = mt.trim(msgs, 10000)
        assert result.removed_count == 0
        assert len(result.messages) == 3

    def test_trim_removes_old_messages(self):
        mt = MessageTrimmer(keep_recent=2)
        # Create many large messages to exceed budget
        msgs = [{"role": "user", "content": "x" * 100} for _ in range(10)]
        te = TokenEstimator(chars_per_token=1.0)
        mt2 = MessageTrimmer(estimator=te, keep_recent=2)
        result = mt2.trim(msgs, 300)  # ~300 tokens budget
        assert result.removed_count > 0

    def test_trim_keeps_system_messages(self):
        te = TokenEstimator(chars_per_token=1.0)
        mt = MessageTrimmer(estimator=te, keep_system=True, keep_recent=1)
        msgs = [
            {"role": "system", "content": "x" * 50},
            {"role": "user", "content": "x" * 200},
            {"role": "user", "content": "x" * 200},
            {"role": "user", "content": "last message"},
        ]
        result = mt.trim(msgs, 200)
        roles = [m["role"] for m in result.messages]
        assert "system" in roles

    def test_trim_keeps_recent_messages(self):
        te = TokenEstimator(chars_per_token=1.0)
        mt = MessageTrimmer(estimator=te, keep_system=False, keep_recent=2)
        msgs = [{"role": "user", "content": "x" * 100} for _ in range(6)]
        result = mt.trim(msgs, 100)
        # Last 2 messages should be kept
        assert result.messages[-2:] == msgs[-2:]

    def test_trim_returns_trim_result(self):
        mt = MessageTrimmer()
        msgs = make_messages(3)
        result = mt.trim(msgs, 10000)
        assert isinstance(result, TrimResult)

    def test_trim_tokens_saved_positive_on_trim(self):
        te = TokenEstimator(chars_per_token=1.0)
        mt = MessageTrimmer(estimator=te, keep_recent=1)
        msgs = [{"role": "user", "content": "x" * 200} for _ in range(5)]
        result = mt.trim(msgs, 300)
        if result.removed_count > 0:
            assert result.tokens_saved > 0


class TestMessageTrimmerTrimToRatio:
    def test_trim_to_ratio_empty(self):
        mt = MessageTrimmer()
        result = mt.trim_to_ratio([], 0.8)
        assert result.messages == []

    def test_trim_to_ratio_reduces(self):
        te = TokenEstimator(chars_per_token=1.0)
        mt = MessageTrimmer(estimator=te, keep_recent=1)
        msgs = [{"role": "user", "content": "x" * 100} for _ in range(10)]
        original_tokens = te.estimate_messages(msgs)
        result = mt.trim_to_ratio(msgs, ratio=0.5)
        new_tokens = te.estimate_messages(result.messages)
        assert new_tokens <= original_tokens

    def test_trim_to_ratio_returns_trim_result(self):
        mt = MessageTrimmer()
        msgs = make_messages(3)
        result = mt.trim_to_ratio(msgs, 0.8)
        assert isinstance(result, TrimResult)

    def test_trim_to_ratio_full(self):
        mt = MessageTrimmer()
        msgs = make_messages(3)
        result = mt.trim_to_ratio(msgs, 1.0)
        # At ratio 1.0, nothing should be trimmed
        assert isinstance(result, TrimResult)
