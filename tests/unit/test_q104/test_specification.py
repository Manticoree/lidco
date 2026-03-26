"""Tests for src/lidco/domain/specification.py — Specification pattern."""
import pytest
from lidco.domain.specification import (
    Specification, AndSpecification, OrSpecification, NotSpecification,
    LambdaSpecification, spec,
)


class IsAdult(Specification):
    def is_satisfied_by(self, candidate) -> bool:
        return candidate.get("age", 0) >= 18


class HasEmail(Specification):
    def is_satisfied_by(self, candidate) -> bool:
        return bool(candidate.get("email"))


class TestSpecificationBasic:
    def test_simple_satisfied(self):
        s = IsAdult()
        assert s.is_satisfied_by({"age": 20}) is True

    def test_simple_not_satisfied(self):
        s = IsAdult()
        assert s.is_satisfied_by({"age": 16}) is False

    def test_and_both_true(self):
        s = IsAdult() & HasEmail()
        assert s.is_satisfied_by({"age": 20, "email": "a@b.com"}) is True

    def test_and_first_false(self):
        s = IsAdult() & HasEmail()
        assert s.is_satisfied_by({"age": 16, "email": "a@b.com"}) is False

    def test_and_second_false(self):
        s = IsAdult() & HasEmail()
        assert s.is_satisfied_by({"age": 20, "email": ""}) is False

    def test_or_first_true(self):
        s = IsAdult() | HasEmail()
        assert s.is_satisfied_by({"age": 20, "email": ""}) is True

    def test_or_both_false(self):
        s = IsAdult() | HasEmail()
        assert s.is_satisfied_by({"age": 16, "email": ""}) is False

    def test_not(self):
        s = ~IsAdult()
        assert s.is_satisfied_by({"age": 16}) is True
        assert s.is_satisfied_by({"age": 20}) is False

    def test_complex_combination(self):
        # adult_with_email: age>=18 AND has email
        # underage: age < 18
        adult_with_email = IsAdult() & HasEmail()
        underage = ~IsAdult()
        s = adult_with_email | underage
        # adult with email → True
        assert s.is_satisfied_by({"age": 20, "email": "x@y.com"}) is True
        # underage → True
        assert s.is_satisfied_by({"age": 16, "email": ""}) is True
        # adult without email AND not underage → False
        assert s.is_satisfied_by({"age": 20, "email": ""}) is False


class TestSpecificationFilter:
    def setup_method(self):
        self.people = [
            {"name": "Alice", "age": 25, "email": "a@a.com"},
            {"name": "Bob", "age": 17, "email": "b@b.com"},
            {"name": "Charlie", "age": 30, "email": ""},
        ]

    def test_filter(self):
        adults = IsAdult().filter(self.people)
        names = [p["name"] for p in adults]
        assert "Alice" in names
        assert "Charlie" in names
        assert "Bob" not in names

    def test_any(self):
        assert HasEmail().any(self.people) is True

    def test_all(self):
        assert IsAdult().all(self.people) is False
        assert IsAdult().all([{"age": 20}, {"age": 25}]) is True

    def test_filter_empty(self):
        assert IsAdult().filter([]) == []


class TestLambdaSpecification:
    def test_lambda_spec(self):
        gt10 = spec(lambda x: x > 10)
        assert gt10.is_satisfied_by(15) is True
        assert gt10.is_satisfied_by(5) is False

    def test_lambda_spec_combined(self):
        gt10 = spec(lambda x: x > 10)
        lt20 = spec(lambda x: x < 20)
        between = gt10 & lt20
        assert between.is_satisfied_by(15) is True
        assert between.is_satisfied_by(25) is False

    def test_spec_shorthand(self):
        even = spec(lambda x: x % 2 == 0, "even numbers")
        assert even.is_satisfied_by(4) is True
        assert even.is_satisfied_by(3) is False
        assert even.description == "even numbers"

    def test_lambda_spec_not(self):
        nonempty = spec(lambda x: bool(x))
        empty = ~nonempty
        assert empty.is_satisfied_by("") is True
        assert empty.is_satisfied_by("text") is False
