"""Tests for src/lidco/patterns/template_method.py — DataProcessor, TextNormalizer, etc."""
import pytest
from lidco.patterns.template_method import (
    DataProcessor, TextNormalizer, NumberPipeline, ReportGenerator,
)


class TestTextNormalizer:
    def test_lowercase(self):
        result = TextNormalizer().process("  Hello World  ")
        assert result == "hello world"

    def test_uppercase(self):
        result = TextNormalizer(uppercase=True).process("hello world")
        assert result == "HELLO WORLD"

    def test_strips_whitespace(self):
        result = TextNormalizer().process("  spaces  ")
        assert result == "spaces"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            TextNormalizer().process("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            TextNormalizer().process("   ")

    def test_non_string_raises(self):
        with pytest.raises(ValueError):
            TextNormalizer().process(42)


class TestNumberPipeline:
    def test_filters_negatives(self):
        result = NumberPipeline().process([1, -2, 3, -4, 5])
        assert "1" in result
        assert "3" in result
        assert "5" in result

    def test_csv_format(self):
        result = NumberPipeline().process([1, 2, 3])
        assert "," in result

    def test_empty_list(self):
        result = NumberPipeline().process([])
        assert result == ""

    def test_all_negatives(self):
        result = NumberPipeline().process([-1, -2, -3])
        assert result == ""

    def test_non_list_raises(self):
        with pytest.raises(ValueError):
            NumberPipeline().process("not a list")

    def test_mixed_types_filters_non_numeric(self):
        result = NumberPipeline().process([1, "two", 3])
        assert "1" in result
        assert "two" not in result


class TestReportGenerator:
    def test_generates_report(self):
        gen = ReportGenerator("My Report")
        result = gen.process("some data")
        assert "My Report" in result
        assert "some data" in result

    def test_post_process_strips(self):
        gen = ReportGenerator("R")
        result = gen.process("data")
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_steps_executed_in_order(self):
        gen = ReportGenerator()
        gen.process("data")
        steps = gen.steps_executed
        assert steps == ["validated", "transformed", "formatted", "post_processed"]

    def test_none_data_raises(self):
        gen = ReportGenerator()
        with pytest.raises(ValueError):
            gen.process(None)
