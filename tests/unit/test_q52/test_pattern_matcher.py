"""Tests for PatternMatcher — Task 353."""

from __future__ import annotations

import pytest

from lidco.analysis.pattern_matcher import PatternKind, PatternMatch, PatternMatcher


SINGLETON_SOURCE = """\
class MyService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
"""

FACTORY_SOURCE = """\
class ShapeFactory:
    def create(self, shape_type: str):
        if shape_type == "circle":
            return Circle()
        return Square()
"""

OBSERVER_SOURCE = """\
class EventBus:
    def __init__(self):
        self._handlers = []

    def subscribe(self, handler):
        self._handlers.append(handler)

    def notify(self, event):
        for h in self._handlers:
            h(event)

    def unsubscribe(self, handler):
        self._handlers.remove(handler)
"""

CONTEXT_MANAGER_SOURCE = """\
class Connection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
"""

ITERATOR_SOURCE = """\
class NumberRange:
    def __init__(self, n):
        self.n = n
        self.current = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.current >= self.n:
            raise StopIteration
        self.current += 1
        return self.current
"""

DECORATOR_SOURCE = """\
class LoggingWrapper:
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def process(self, data):
        print("logging")
        return self._wrapped.process(data)
"""

PLAIN_CLASS = """\
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
"""

SYNTAX_ERROR = "def broken(:"


class TestPatternMatch:
    def test_frozen(self):
        pm = PatternMatch(
            kind=PatternKind.SINGLETON, symbol="S", file="x.py",
            line=1, confidence=0.8, evidence="found",
        )
        with pytest.raises((AttributeError, TypeError)):
            pm.symbol = "X"  # type: ignore[misc]


class TestPatternMatcher:
    def setup_method(self):
        self.matcher = PatternMatcher()

    def test_empty_source(self):
        assert self.matcher.detect("") == []

    def test_syntax_error(self):
        assert self.matcher.detect(SYNTAX_ERROR) == []

    def test_singleton_detected(self):
        results = self.matcher.detect(SINGLETON_SOURCE)
        kinds = {r.kind for r in results}
        assert PatternKind.SINGLETON in kinds

    def test_factory_detected(self):
        results = self.matcher.detect(FACTORY_SOURCE)
        kinds = {r.kind for r in results}
        assert PatternKind.FACTORY in kinds

    def test_observer_detected(self):
        results = self.matcher.detect(OBSERVER_SOURCE)
        kinds = {r.kind for r in results}
        assert PatternKind.OBSERVER in kinds

    def test_context_manager_detected(self):
        results = self.matcher.detect(CONTEXT_MANAGER_SOURCE)
        kinds = {r.kind for r in results}
        assert PatternKind.CONTEXT_MANAGER in kinds

    def test_context_manager_confidence_1(self):
        results = self.matcher.detect(CONTEXT_MANAGER_SOURCE)
        cm = next(r for r in results if r.kind == PatternKind.CONTEXT_MANAGER)
        assert cm.confidence == 1.0

    def test_iterator_detected(self):
        results = self.matcher.detect(ITERATOR_SOURCE)
        kinds = {r.kind for r in results}
        assert PatternKind.ITERATOR in kinds

    def test_decorator_pattern_detected(self):
        results = self.matcher.detect(DECORATOR_SOURCE)
        kinds = {r.kind for r in results}
        assert PatternKind.DECORATOR_PATTERN in kinds

    def test_plain_class_no_pattern(self):
        results = self.matcher.detect(PLAIN_CLASS)
        assert results == []

    def test_symbol_name_recorded(self):
        results = self.matcher.detect(CONTEXT_MANAGER_SOURCE)
        cm = next(r for r in results if r.kind == PatternKind.CONTEXT_MANAGER)
        assert cm.symbol == "Connection"

    def test_file_path_recorded(self):
        results = self.matcher.detect(CONTEXT_MANAGER_SOURCE, file_path="conn.py")
        assert all(r.file == "conn.py" for r in results)

    def test_confidence_between_0_and_1(self):
        results = self.matcher.detect(SINGLETON_SOURCE)
        for r in results:
            assert 0.0 <= r.confidence <= 1.0
