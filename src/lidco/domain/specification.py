"""Specification pattern — composable business rules (stdlib only)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class Specification(ABC):
    """
    Abstract base for composable specifications (business rules).

    Specifications can be combined via ``&`` (And), ``|`` (Or), ``~`` (Not).
    """

    @abstractmethod
    def is_satisfied_by(self, candidate: Any) -> bool:
        """Return True if *candidate* satisfies this specification."""

    def __and__(self, other: "Specification") -> "AndSpecification":
        return AndSpecification(self, other)

    def __or__(self, other: "Specification") -> "OrSpecification":
        return OrSpecification(self, other)

    def __invert__(self) -> "NotSpecification":
        return NotSpecification(self)

    def filter(self, candidates: list) -> list:
        """Return all candidates satisfying this specification."""
        return [c for c in candidates if self.is_satisfied_by(c)]

    def any(self, candidates: list) -> bool:
        return any(self.is_satisfied_by(c) for c in candidates)

    def all(self, candidates: list) -> bool:
        return all(self.is_satisfied_by(c) for c in candidates)


class AndSpecification(Specification):
    def __init__(self, *specs: Specification) -> None:
        self._specs = specs

    def is_satisfied_by(self, candidate: Any) -> bool:
        return all(s.is_satisfied_by(candidate) for s in self._specs)


class OrSpecification(Specification):
    def __init__(self, *specs: Specification) -> None:
        self._specs = specs

    def is_satisfied_by(self, candidate: Any) -> bool:
        return any(s.is_satisfied_by(candidate) for s in self._specs)


class NotSpecification(Specification):
    def __init__(self, spec: Specification) -> None:
        self._spec = spec

    def is_satisfied_by(self, candidate: Any) -> bool:
        return not self._spec.is_satisfied_by(candidate)


class LambdaSpecification(Specification):
    """Convenience wrapper for inline predicate functions."""

    def __init__(self, predicate: Callable[[Any], bool], description: str = "") -> None:
        self._predicate = predicate
        self.description = description

    def is_satisfied_by(self, candidate: Any) -> bool:
        return bool(self._predicate(candidate))


def spec(predicate: Callable[[Any], bool], description: str = "") -> LambdaSpecification:
    """Shorthand to create a :class:`LambdaSpecification`."""
    return LambdaSpecification(predicate, description)
