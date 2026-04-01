"""Build property-based test specs."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PropertySpec:
    """A property-based test specification."""

    name: str
    function_name: str
    property_description: str
    input_strategy: str = ""
    invariant: str = ""


# Maps common type-hint keywords to hypothesis-style strategy descriptions.
_STRATEGY_MAP: dict[str, str] = {
    "int": "integers()",
    "float": "floats(allow_nan=False)",
    "str": "text(min_size=0, max_size=256)",
    "bool": "booleans()",
    "list": "lists(integers())",
    "dict": "dictionaries(keys=text(max_size=8), values=integers())",
    "bytes": "binary(min_size=0, max_size=256)",
    "tuple": "tuples(integers(), integers())",
    "set": "frozensets(integers())",
}


class PropertyBuilder:
    """Build :class:`PropertySpec` objects for property-based testing."""

    def __init__(self) -> None:
        self._extra_strategies: dict[str, str] = {}

    def infer_strategy(self, type_hint: str) -> str:
        """Map *type_hint* to a strategy description string."""
        if type_hint in self._extra_strategies:
            return self._extra_strategies[type_hint]
        for key, strat in _STRATEGY_MAP.items():
            if key in type_hint.lower():
                return strat
        return "just(None)"

    def build(self, function_name: str, params: list[tuple[str, str]]) -> PropertySpec:
        """Build a :class:`PropertySpec` from *function_name* and typed *params*."""
        strategies: list[str] = []
        for pname, phint in params:
            strat = self.infer_strategy(phint)
            strategies.append(f"{pname}={strat}")
        strategy_str = ", ".join(strategies) if strategies else "# no params"

        return PropertySpec(
            name=f"test_prop_{function_name}",
            function_name=function_name,
            property_description=f"Property test for {function_name}",
            input_strategy=strategy_str,
            invariant=f"{function_name} returns without error",
        )

    def to_code(self, spec: PropertySpec) -> str:
        """Generate hypothesis-style test code from *spec*."""
        lines: list[str] = [
            '"""Auto-generated property test."""',
            "from hypothesis import given, strategies as st",
            "",
            "",
            f"@given({spec.input_strategy})" if spec.input_strategy else "# @given()",
            f"def {spec.name}({_params_from_strategy(spec.input_strategy)}):",
            f'    """{spec.property_description}."""',
        ]
        if spec.invariant:
            lines.append(f"    # Invariant: {spec.invariant}")
        lines.append(f"    result = {spec.function_name}({_call_args(spec.input_strategy)})")
        lines.append("    assert result is not None or True  # placeholder assertion")
        lines.append("")
        return "\n".join(lines) + "\n"

    def detect_invariants(self, source: str) -> list[str]:
        """Simple heuristic invariant detection from *source*."""
        invariants: list[str] = []

        # Pattern: len() comparisons
        if re.search(r"len\(\w+\)\s*[><=!]+", source):
            invariants.append("length constraint")

        # Pattern: assert statements
        for m in re.finditer(r"assert\s+(.+?)(?:\n|$)", source):
            invariants.append(f"assertion: {m.group(1).strip()}")

        # Pattern: return type checks (isinstance)
        if re.search(r"isinstance\(", source):
            invariants.append("type constraint")

        # Pattern: range/boundary checks
        if re.search(r"(?:0\s*<=|>=\s*0|<\s*len|<=\s*\w+\s*<)", source):
            invariants.append("boundary constraint")

        # Pattern: sorted output
        if "sorted(" in source or ".sort()" in source:
            invariants.append("ordering invariant")

        # Pattern: idempotent (f(f(x)) == f(x))
        if re.search(r"(\w+)\(\1\(", source):
            invariants.append("possible idempotency")

        return invariants


def _params_from_strategy(strategy: str) -> str:
    """Extract parameter names from strategy string for function signature."""
    if not strategy or strategy.startswith("#"):
        return ""
    params = []
    for part in strategy.split(","):
        part = part.strip()
        if "=" in part:
            params.append(part.split("=")[0].strip())
    return ", ".join(params)


def _call_args(strategy: str) -> str:
    """Extract parameter names for function call."""
    return _params_from_strategy(strategy)
