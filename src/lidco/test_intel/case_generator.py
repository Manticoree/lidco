"""Generate unit test cases from function signatures."""
from __future__ import annotations

import ast
import re
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TestCase:
    """A single generated test case."""

    name: str
    function_name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    expected: Any = None
    assertion: str = "assertEqual"
    description: str = ""


# Default edge-case values keyed by type-hint keyword.
_DEFAULT_EDGE: dict[str, list[Any]] = {
    "str": ["", "a", " " * 100],
    "int": [0, -1, 1, 2**31 - 1],
    "float": [0.0, -1.0, 1.0, float("inf")],
    "bool": [True, False],
    "list": [[], [None]],
    "dict": [{}, {"k": "v"}],
    "None": [None],
    "NoneType": [None],
}


class TestCaseGenerator:
    """Generate :class:`TestCase` instances from Python source code."""

    def __init__(self) -> None:
        self._extra_patterns: dict[str, list[Any]] = {}

    # ------------------------------------------------------------------
    # public helpers
    # ------------------------------------------------------------------

    def add_pattern(self, type_hint: str, values: list[Any]) -> None:
        """Extend known edge-case values for *type_hint*."""
        existing = self._extra_patterns.get(type_hint, [])
        self._extra_patterns[type_hint] = existing + list(values)

    # ------------------------------------------------------------------
    # generation
    # ------------------------------------------------------------------

    def generate(self, source: str, function_name: str = "") -> list[TestCase]:
        """Parse *source*, generate edge-case :class:`TestCase` objects.

        If *function_name* is given, only generate for that function.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        cases: list[TestCase] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if function_name and node.name != function_name:
                continue
            params = self._extract_params(node)
            edge_sets = self.generate_edge_cases(params)
            for idx, inputs in enumerate(edge_sets):
                case = TestCase(
                    name=f"test_{node.name}_edge_{idx}",
                    function_name=node.name,
                    inputs=inputs,
                    expected=None,
                    assertion="assertEqual",
                    description=f"Edge case {idx} for {node.name}",
                )
                cases.append(case)
        return cases

    def generate_edge_cases(self, params: list[tuple[str, str]]) -> list[dict[str, Any]]:
        """Return a list of input-dicts covering null / empty / boundary values."""
        if not params:
            return [{}]

        per_param: dict[str, list[Any]] = {}
        for name, hint in params:
            values = self._values_for_hint(hint)
            per_param[name] = values

        # Cartesian product is too large; use zip-longest style with cycling.
        max_len = max(len(v) for v in per_param.values()) if per_param else 1
        result: list[dict[str, Any]] = []
        for i in range(max_len):
            combo: dict[str, Any] = {}
            for pname, vals in per_param.items():
                combo[pname] = vals[i % len(vals)]
            result.append(combo)
        return result

    def to_code(self, cases: list[TestCase], class_name: str = "TestGenerated") -> str:
        """Generate pytest-style test code from *cases*."""
        lines: list[str] = [
            '"""Auto-generated tests."""',
            "import unittest",
            "",
            "",
            f"class {class_name}(unittest.TestCase):",
        ]
        if not cases:
            lines.append("    pass")
            return "\n".join(lines) + "\n"

        for case in cases:
            lines.append(f"    def {case.name}(self):")
            if case.description:
                lines.append(f'        """{case.description}."""')
            args_str = ", ".join(f"{k}={v!r}" for k, v in case.inputs.items())
            lines.append(f"        result = {case.function_name}({args_str})")
            if case.expected is not None:
                lines.append(f"        self.{case.assertion}(result, {case.expected!r})")
            else:
                lines.append("        # TODO: add expected value")
            lines.append("")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_params(node: ast.FunctionDef) -> list[tuple[str, str]]:
        """Return [(param_name, type_hint_str), ...] from an AST function node."""
        params: list[tuple[str, str]] = []
        for arg in node.args.args:
            if arg.arg == "self":
                continue
            hint = ""
            if arg.annotation:
                hint = ast.unparse(arg.annotation)
            params.append((arg.arg, hint))
        return params

    def _values_for_hint(self, hint: str) -> list[Any]:
        """Look up edge-case values for *hint*."""
        # Check extra patterns first.
        if hint in self._extra_patterns:
            return list(self._extra_patterns[hint])

        # Match against built-in defaults.
        for key, vals in _DEFAULT_EDGE.items():
            if key in hint.lower():
                return list(vals)

        # Fallback for unknown hints.
        return [None, 0, ""]
