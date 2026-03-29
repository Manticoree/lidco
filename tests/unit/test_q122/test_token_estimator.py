"""Tests for src/lidco/context/token_estimator.py."""
from lidco.context.token_estimator import TokenEstimator


class TestTokenEstimatorInit:
    def test_default_chars_per_token(self):
        te = TokenEstimator()
        assert te.chars_per_token == 4.0

    def test_custom_chars_per_token(self):
        te = TokenEstimator(chars_per_token=3.5)
        assert te.chars_per_token == 3.5

    def test_chars_per_token_property(self):
        te = TokenEstimator(chars_per_token=5.0)
        assert te.chars_per_token == 5.0


class TestTokenEstimatorEstimate:
    def test_estimate_empty_string(self):
        te = TokenEstimator()
        assert te.estimate("") == 0

    def test_estimate_short_string(self):
        te = TokenEstimator()
        result = te.estimate("abcd")  # 4 chars / 4 = 1
        assert result == 1

    def test_estimate_longer_string(self):
        te = TokenEstimator()
        result = te.estimate("a" * 100)
        assert result == 25

    def test_estimate_returns_int(self):
        te = TokenEstimator()
        result = te.estimate("hello world")
        assert isinstance(result, int)

    def test_estimate_minimum_one(self):
        te = TokenEstimator()
        result = te.estimate("a")  # 1 char / 4 = 0.25 → min 1
        assert result >= 1

    def test_estimate_custom_ratio(self):
        te = TokenEstimator(chars_per_token=2.0)
        result = te.estimate("ab")  # 2 / 2 = 1
        assert result == 1


class TestTokenEstimatorEstimateMessages:
    def test_estimate_messages_empty(self):
        te = TokenEstimator()
        result = te.estimate_messages([])
        assert result == 0

    def test_estimate_messages_single(self):
        te = TokenEstimator()
        msgs = [{"role": "user", "content": "hello world"}]
        result = te.estimate_messages(msgs)
        assert result > 0

    def test_estimate_messages_multiple(self):
        te = TokenEstimator()
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        result = te.estimate_messages(msgs)
        assert result > 0

    def test_estimate_messages_system(self):
        te = TokenEstimator()
        msgs = [{"role": "system", "content": "You are an AI assistant."}]
        result = te.estimate_messages(msgs)
        assert result > 0

    def test_estimate_messages_overhead(self):
        te = TokenEstimator()
        # Two messages should be > one message with same total content
        m1 = [{"role": "user", "content": "hello"}]
        m2 = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": ""}]
        assert te.estimate_messages(m2) > te.estimate_messages(m1)


class TestTokenEstimatorEstimateDict:
    def test_estimate_dict_string(self):
        te = TokenEstimator()
        result = te.estimate_dict("hello world")
        assert result > 0

    def test_estimate_dict_dict(self):
        te = TokenEstimator()
        result = te.estimate_dict({"key": "value", "other": "data"})
        assert result > 0

    def test_estimate_dict_list(self):
        te = TokenEstimator()
        result = te.estimate_dict(["a", "b", "c"])
        assert result > 0

    def test_estimate_dict_nested(self):
        te = TokenEstimator()
        result = te.estimate_dict({"nested": {"deep": "value"}})
        assert result > 0

    def test_estimate_dict_number(self):
        te = TokenEstimator()
        result = te.estimate_dict(42)
        assert isinstance(result, int)


class TestTokenEstimatorCalibrate:
    def test_calibrate_updates_ratio(self):
        te = TokenEstimator(chars_per_token=4.0)
        samples = [("hello world", 3), ("abc", 1)]
        te.calibrate(samples)
        assert te.chars_per_token != 4.0

    def test_calibrate_empty_samples(self):
        te = TokenEstimator(chars_per_token=4.0)
        te.calibrate([])
        assert te.chars_per_token == 4.0

    def test_calibrate_single_sample(self):
        te = TokenEstimator()
        te.calibrate([("abcdef", 3)])  # 6 chars / 3 tokens = 2.0
        assert abs(te.chars_per_token - 2.0) < 0.01

    def test_calibrate_multiple_samples(self):
        te = TokenEstimator()
        # 8 total chars, 4 total tokens = 2.0
        samples = [("abcd", 2), ("efgh", 2)]
        te.calibrate(samples)
        assert abs(te.chars_per_token - 2.0) < 0.01
