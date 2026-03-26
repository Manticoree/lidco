"""Tests for src/lidco/patterns/decorator_pattern.py — Component decorators."""
import pytest
from lidco.patterns.decorator_pattern import (
    ConcreteComponent, UpperCaseDecorator, PrefixDecorator, SuffixDecorator,
    CachingDecorator, LoggingDecorator,
)


class TestConcreteComponent:
    def test_operation(self):
        c = ConcreteComponent("hello")
        assert c.operation() == "hello"

    def test_description(self):
        c = ConcreteComponent("hello")
        assert c.description == "hello"


class TestUpperCaseDecorator:
    def test_uppercases(self):
        d = UpperCaseDecorator(ConcreteComponent("hello"))
        assert d.operation() == "HELLO"

    def test_description(self):
        d = UpperCaseDecorator(ConcreteComponent("x"))
        assert "UpperCase" in d.description

    def test_wrapped(self):
        c = ConcreteComponent("x")
        d = UpperCaseDecorator(c)
        assert d.wrapped is c


class TestPrefixDecorator:
    def test_prepends(self):
        d = PrefixDecorator(ConcreteComponent("hello"), ">>> ")
        assert d.operation() == ">>> hello"

    def test_description(self):
        d = PrefixDecorator(ConcreteComponent("x"), ">>")
        assert "Prefix" in d.description


class TestSuffixDecorator:
    def test_appends(self):
        d = SuffixDecorator(ConcreteComponent("hello"), "!")
        assert d.operation() == "hello!"

    def test_description(self):
        d = SuffixDecorator(ConcreteComponent("x"), "!")
        assert "Suffix" in d.description


class TestCachingDecorator:
    def test_caches_result(self):
        call_count = [0]

        class Counter(ConcreteComponent):
            def operation(self):
                call_count[0] += 1
                return "result"

        d = CachingDecorator(Counter("x"))
        assert d.operation() == "result"
        assert d.operation() == "result"
        assert call_count[0] == 1  # inner called only once

    def test_call_count(self):
        d = CachingDecorator(ConcreteComponent("x"))
        d.operation()
        d.operation()
        d.operation()
        assert d.call_count == 3

    def test_invalidate(self):
        call_count = [0]

        class Counter(ConcreteComponent):
            def operation(self):
                call_count[0] += 1
                return "result"

        d = CachingDecorator(Counter("x"))
        d.operation()
        d.invalidate()
        d.operation()
        assert call_count[0] == 2

    def test_description(self):
        d = CachingDecorator(ConcreteComponent("x"))
        assert "Caching" in d.description


class TestLoggingDecorator:
    def test_logs_result(self):
        d = LoggingDecorator(ConcreteComponent("hello"))
        d.operation()
        d.operation()
        assert d.log == ["hello", "hello"]

    def test_returns_result(self):
        d = LoggingDecorator(ConcreteComponent("x"))
        assert d.operation() == "x"

    def test_description(self):
        d = LoggingDecorator(ConcreteComponent("x"))
        assert "Logging" in d.description


class TestDecoratorChaining:
    def test_chain_upper_then_prefix(self):
        d = PrefixDecorator(UpperCaseDecorator(ConcreteComponent("hello")), ">>> ")
        assert d.operation() == ">>> HELLO"

    def test_chain_prefix_then_suffix(self):
        d = SuffixDecorator(PrefixDecorator(ConcreteComponent("x"), "["), "]")
        assert d.operation() == "[x]"

    def test_deep_chain(self):
        c = ConcreteComponent("base")
        c = PrefixDecorator(c, "A")
        c = SuffixDecorator(c, "Z")
        c = UpperCaseDecorator(c)
        assert c.operation() == "ABASEZ"
