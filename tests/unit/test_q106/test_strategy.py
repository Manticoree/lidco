"""Tests for src/lidco/patterns/strategy.py — Strategy, Context."""
import pytest
from lidco.patterns.strategy import (
    Strategy, Context, LambdaStrategy,
    AscendingSortStrategy, DescendingSortStrategy, KeySortStrategy,
    CompressionStrategy, NoCompressionStrategy, RLECompressionStrategy,
)


class TestContext:
    def test_set_and_execute(self):
        ctx = Context(AscendingSortStrategy())
        result = ctx.execute([3, 1, 2])
        assert result == [1, 2, 3]

    def test_swap_strategy(self):
        ctx = Context(AscendingSortStrategy())
        ctx.set_strategy(DescendingSortStrategy())
        result = ctx.execute([3, 1, 2])
        assert result == [3, 2, 1]

    def test_no_strategy_raises(self):
        ctx = Context()
        with pytest.raises(RuntimeError):
            ctx.execute([1, 2, 3])

    def test_strategy_history(self):
        ctx = Context()
        ctx.set_strategy(AscendingSortStrategy())
        ctx.set_strategy(DescendingSortStrategy())
        assert len(ctx.strategy_history) == 2

    def test_current_strategy(self):
        s = AscendingSortStrategy()
        ctx = Context(s)
        assert ctx.current_strategy is s


class TestSortStrategies:
    def test_ascending(self):
        s = AscendingSortStrategy()
        assert s.execute([3, 1, 2]) == [1, 2, 3]

    def test_descending(self):
        s = DescendingSortStrategy()
        assert s.execute([3, 1, 2]) == [3, 2, 1]

    def test_ascending_strings(self):
        s = AscendingSortStrategy()
        assert s.execute(["banana", "apple", "cherry"]) == ["apple", "banana", "cherry"]

    def test_key_sort(self):
        s = KeySortStrategy(key=len)
        result = s.execute(["banana", "apple", "fig"])
        assert result[0] == "fig"

    def test_key_sort_reverse(self):
        s = KeySortStrategy(key=len, reverse=True)
        result = s.execute(["fig", "banana", "apple"])
        assert result[0] == "banana"

    def test_original_not_mutated(self):
        original = [3, 1, 2]
        AscendingSortStrategy().execute(original)
        assert original == [3, 1, 2]

    def test_strategy_name(self):
        s = AscendingSortStrategy()
        assert s.name == "AscendingSortStrategy"


class TestLambdaStrategy:
    def test_wraps_callable(self):
        s = LambdaStrategy(lambda x: x * 2, "double")
        assert s.execute(5) == 10

    def test_name(self):
        s = LambdaStrategy(lambda x: x, "my_strategy")
        assert s.name == "my_strategy"


class TestCompressionStrategies:
    def test_no_compression(self):
        s = NoCompressionStrategy()
        assert s.execute("hello") == "hello"

    def test_rle_repeated(self):
        s = RLECompressionStrategy()
        result = s.execute("aaabbbcc")
        assert "3a" in result
        assert "3b" in result
        assert "2c" in result

    def test_rle_single_chars(self):
        s = RLECompressionStrategy()
        result = s.execute("abc")
        assert "a" in result
        assert "b" in result
        assert "c" in result
        assert "1" not in result  # single chars not prefixed with 1

    def test_rle_empty(self):
        s = RLECompressionStrategy()
        assert s.execute("") == ""
