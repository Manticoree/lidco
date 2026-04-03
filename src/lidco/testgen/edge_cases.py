"""Edge case generator — produce boundary/edge-case inputs for test params (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EdgeCase:
    """A single edge-case input value."""

    input_value: Any
    description: str
    category: str


_TYPE_EDGES: dict[str, list[EdgeCase]] = {
    "int": [
        EdgeCase(0, "zero", "boundary"),
        EdgeCase(-1, "negative one", "boundary"),
        EdgeCase(1, "one", "boundary"),
        EdgeCase(2**31 - 1, "max 32-bit signed", "overflow"),
        EdgeCase(-(2**31), "min 32-bit signed", "overflow"),
    ],
    "float": [
        EdgeCase(0.0, "zero float", "boundary"),
        EdgeCase(-0.0, "negative zero", "boundary"),
        EdgeCase(float("inf"), "positive infinity", "special"),
        EdgeCase(float("-inf"), "negative infinity", "special"),
        EdgeCase(float("nan"), "not a number", "special"),
        EdgeCase(1e-10, "very small positive", "precision"),
    ],
    "str": [
        EdgeCase("", "empty string", "empty"),
        EdgeCase(" ", "single space", "whitespace"),
        EdgeCase("  \t\n", "whitespace mix", "whitespace"),
        EdgeCase("a" * 1000, "long string", "overflow"),
        EdgeCase("\x00", "null byte", "special"),
        EdgeCase("<script>", "html tag", "injection"),
    ],
    "list": [
        EdgeCase([], "empty list", "empty"),
        EdgeCase([None], "list with None", "null"),
        EdgeCase([1], "single element", "boundary"),
        EdgeCase(list(range(1000)), "large list", "overflow"),
    ],
    "dict": [
        EdgeCase({}, "empty dict", "empty"),
        EdgeCase({"": ""}, "empty key and value", "boundary"),
        EdgeCase({None: None}, "None key and value", "null"),
    ],
    "bool": [
        EdgeCase(True, "true", "boundary"),
        EdgeCase(False, "false", "boundary"),
    ],
}

_CATEGORIES = sorted({ec.category for edges in _TYPE_EDGES.values() for ec in edges})


class EdgeCaseGenerator:
    """Generate edge-case inputs for testing."""

    def for_type(self, type_name: str) -> list[EdgeCase]:
        """Return edge cases for a given type name."""
        return list(_TYPE_EDGES.get(type_name, []))

    def for_function(self, params: list[dict]) -> list[list[EdgeCase]]:
        """Return edge cases per parameter.

        Each dict in *params* should have at least ``{"name": ..., "type": ...}``.
        """
        result: list[list[EdgeCase]] = []
        for param in params:
            type_name = param.get("type", "str")
            result.append(self.for_type(type_name))
        return result

    def boundary_values(self, min_val: int, max_val: int) -> list[int]:
        """Return boundary values for range [*min_val*, *max_val*]."""
        values = [
            min_val - 1,
            min_val,
            min_val + 1,
            max_val - 1,
            max_val,
            max_val + 1,
        ]
        midpoint = (min_val + max_val) // 2
        if midpoint not in values:
            values.append(midpoint)
        return sorted(values)

    def categories(self) -> list[str]:
        """Return all known edge case categories."""
        return list(_CATEGORIES)
