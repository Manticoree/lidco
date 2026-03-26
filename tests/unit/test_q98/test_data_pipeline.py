"""Tests for T625 DataPipeline."""
import pytest

from lidco.data.pipeline import (
    DataPipeline,
    FilterStep,
    LimitStep,
    MapStep,
    SortStep,
    StepResult,
    UniqueStep,
)


class TestFilterStep:
    def test_keeps_matching(self):
        step = FilterStep(lambda x: x % 2 == 0)
        assert step.process([1, 2, 3, 4]) == [2, 4]

    def test_empty_input(self):
        step = FilterStep(lambda x: x > 0)
        assert step.process([]) == []

    def test_name_attribute(self):
        step = FilterStep(lambda x: True, name="my_filter")
        assert step.name == "my_filter"

    def test_default_name(self):
        step = FilterStep(lambda x: True)
        assert step.name == "filter"


class TestMapStep:
    def test_doubles(self):
        step = MapStep(lambda x: x * 2)
        assert step.process([1, 2, 3]) == [2, 4, 6]

    def test_string_transform(self):
        step = MapStep(str.upper)
        assert step.process(["a", "b"]) == ["A", "B"]

    def test_empty_input(self):
        step = MapStep(lambda x: x)
        assert step.process([]) == []


class TestSortStep:
    def test_ascending(self):
        step = SortStep()
        assert step.process([3, 1, 2]) == [1, 2, 3]

    def test_descending(self):
        step = SortStep(reverse=True)
        assert step.process([1, 2, 3]) == [3, 2, 1]

    def test_by_key(self):
        step = SortStep(key=lambda x: x["age"])
        data = [{"age": 30}, {"age": 20}, {"age": 25}]
        result = step.process(data)
        assert result[0]["age"] == 20

    def test_does_not_mutate(self):
        original = [3, 1, 2]
        step = SortStep()
        step.process(original)
        assert original == [3, 1, 2]


class TestLimitStep:
    def test_limits(self):
        step = LimitStep(2)
        assert step.process([1, 2, 3, 4]) == [1, 2]

    def test_zero_limit(self):
        step = LimitStep(0)
        assert step.process([1, 2, 3]) == []

    def test_limit_larger_than_data(self):
        step = LimitStep(100)
        assert step.process([1, 2]) == [1, 2]

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            LimitStep(-1)


class TestUniqueStep:
    def test_dedup_simple(self):
        step = UniqueStep()
        assert step.process([1, 2, 2, 3, 1]) == [1, 2, 3]

    def test_preserves_order(self):
        step = UniqueStep()
        assert step.process([3, 1, 3, 2]) == [3, 1, 2]

    def test_with_key(self):
        step = UniqueStep(key=lambda x: x["id"])
        data = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}, {"id": 1, "v": "c"}]
        result = step.process(data)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    def test_empty(self):
        step = UniqueStep()
        assert step.process([]) == []


class TestDataPipeline:
    def test_run_chained(self):
        pipeline = (
            DataPipeline("test")
            .add_step(FilterStep(lambda x: x > 0))
            .add_step(MapStep(lambda x: x * 2))
            .add_step(LimitStep(3))
        )
        result = pipeline.run([-1, 1, 2, 3, 4, 5])
        assert result == [2, 4, 6]

    def test_run_empty_raises(self):
        p = DataPipeline()
        with pytest.raises(RuntimeError, match="no steps"):
            p.run([1, 2, 3])

    def test_add_step_returns_self(self):
        p = DataPipeline()
        step = FilterStep(lambda x: True)
        returned = p.add_step(step)
        assert returned is p

    def test_steps_returns_copy(self):
        p = DataPipeline()
        p.add_step(FilterStep(lambda x: True))
        steps_copy = p.steps
        steps_copy.clear()
        assert len(p.steps) == 1

    def test_clear_removes_steps(self):
        p = DataPipeline().add_step(FilterStep(lambda x: True))
        p.clear()
        assert p.steps == []

    def test_dry_run_counts(self):
        pipeline = (
            DataPipeline("dry")
            .add_step(FilterStep(lambda x: x > 0, name="pos_filter"))
            .add_step(LimitStep(2, name="top2"))
        )
        results = pipeline.dry_run([-1, 1, 2, 3])
        assert len(results) == 2
        assert results[0].step_name == "pos_filter"
        assert results[0].input_count == 4
        assert results[0].output_count == 3
        assert results[1].step_name == "top2"
        assert results[1].input_count == 3
        assert results[1].output_count == 2

    def test_dry_run_empty_steps(self):
        p = DataPipeline()
        # Should return empty list, not raise
        results = p.dry_run([1, 2, 3])
        assert results == []

    def test_name_attribute(self):
        p = DataPipeline("my_pipeline")
        assert p.name == "my_pipeline"

    def test_sort_unique_pipeline(self):
        pipeline = (
            DataPipeline()
            .add_step(UniqueStep())
            .add_step(SortStep())
        )
        result = pipeline.run([3, 1, 2, 1, 3])
        assert result == [1, 2, 3]
