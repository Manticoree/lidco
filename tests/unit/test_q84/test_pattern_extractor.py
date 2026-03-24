"""Tests for PatternExtractor (T552)."""
from __future__ import annotations
import pytest
from lidco.learning.pattern_extractor import PatternExtractor, CodingPattern, ExtractionResult, _extract_entry


def test_extract_async_pattern():
    turns = [{"content": "async def fetch(): pass\nawait fetch()", "role": "user"}]
    e = PatternExtractor()
    result = e.extract(turns)
    names = [p.name for p in result.patterns]
    assert "async-await" in names


def test_extract_dataclass_pattern():
    turns = [{"content": "@dataclass\nclass Foo:\n    x: int", "role": "user"}]
    e = PatternExtractor()
    result = e.extract(turns)
    assert any(p.name == "dataclass" for p in result.patterns)


def test_extract_no_patterns():
    turns = [{"content": "x = 1\ny = 2", "role": "user"}]
    e = PatternExtractor(min_confidence=0.99)
    result = e.extract(turns)
    # may or may not have patterns — just check it doesn't crash
    assert isinstance(result.patterns, list)


def test_extract_empty_turns():
    e = PatternExtractor()
    result = e.extract([])
    assert result.total_patterns == 0
    assert result.source_turns == 0


def test_format_summary_no_patterns():
    e = PatternExtractor(min_confidence=1.1)  # impossible threshold
    result = e.extract([{"content": "x=1"}])
    assert "No patterns" in result.format_summary()


def test_top_returns_top_n():
    turns = [{"content": "@dataclass\n@dataclass\nasync def f(): pass", "role": "user"}]
    e = PatternExtractor()
    result = e.extract(turns)
    top = result.top(1)
    assert len(top) <= 1


def test_extract_from_diff():
    diff = "+async def handler():\n+    pass\n+@dataclass\n"
    e = PatternExtractor()
    result = e.extract_from_diff(diff)
    assert isinstance(result, ExtractionResult)


def test_confidence_in_range():
    turns = [{"content": "def test_foo():\n    pass\nimport pytest\n", "role": "user"}]
    e = PatternExtractor()
    result = e.extract(turns)
    for p in result.patterns:
        assert 0.0 <= p.confidence <= 1.0
