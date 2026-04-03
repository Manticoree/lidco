"""Mock generator v2 — generate mock class code from specs (stdlib only)."""
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MockSpec:
    """Specification for a mock class."""

    name: str
    methods: list[dict] = field(default_factory=list)
    return_values: dict[str, Any] = field(default_factory=dict)


class MockGeneratorV2:
    """Generate mock and spy classes from specifications."""

    def generate(self, spec: MockSpec) -> str:
        """Return Python mock class code for *spec*."""
        lines: list[str] = [
            f"class Mock{spec.name}:",
            f'    """Auto-generated mock for {spec.name}."""',
            "",
        ]

        if not spec.methods:
            lines.append("    pass")
            return "\n".join(lines) + "\n"

        # __init__
        lines.append("    def __init__(self):")
        lines.append("        self._calls = {}")
        for method in spec.methods:
            name = method.get("name", "unknown")
            lines.append(f"        self._calls[{name!r}] = []")
        lines.append("")

        for method in spec.methods:
            name = method.get("name", "unknown")
            params_list = method.get("params", [])
            is_async = method.get("is_async", False)
            ret = spec.return_values.get(name, "None")

            param_str = ", ".join(["self"] + params_list)
            prefix = "async " if is_async else ""
            lines.append(f"    {prefix}def {name}({param_str}):")
            lines.append(f"        self._calls[{name!r}].append(({', '.join(params_list)},))" if params_list else f"        self._calls[{name!r}].append(())")
            lines.append(f"        return {ret!r}")
            lines.append("")

        return "\n".join(lines) + "\n"

    def from_interface(self, source: str, class_name: str) -> MockSpec:
        """Parse *source* and extract a MockSpec for *class_name*."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return MockSpec(name=class_name)

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.ClassDef) or node.name != class_name:
                continue
            methods: list[dict] = []
            for item in ast.iter_child_nodes(node):
                if isinstance(item, ast.AsyncFunctionDef):
                    params = [
                        a.arg for a in item.args.args if a.arg != "self"
                    ]
                    methods.append({"name": item.name, "params": params, "is_async": True})
                elif isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    params = [
                        a.arg for a in item.args.args if a.arg != "self"
                    ]
                    methods.append({"name": item.name, "params": params, "is_async": False})
            return MockSpec(name=class_name, methods=methods)

        return MockSpec(name=class_name)

    def generate_spy(self, spec: MockSpec) -> str:
        """Return Python spy class code that records calls for *spec*."""
        lines: list[str] = [
            f"class Spy{spec.name}:",
            f'    """Auto-generated spy for {spec.name}."""',
            "",
        ]

        if not spec.methods:
            lines.append("    pass")
            return "\n".join(lines) + "\n"

        lines.append("    def __init__(self):")
        lines.append("        self.call_log = []")
        lines.append("")

        for method in spec.methods:
            name = method.get("name", "unknown")
            params_list = method.get("params", [])
            is_async = method.get("is_async", False)
            ret = spec.return_values.get(name, "None")

            param_str = ", ".join(["self"] + params_list)
            prefix = "async " if is_async else ""
            args_dict = ", ".join(f"{p!r}: {p}" for p in params_list) if params_list else ""
            lines.append(f"    {prefix}def {name}({param_str}):")
            lines.append(f"        self.call_log.append({{'method': {name!r}, 'args': {{{args_dict}}}}})")
            lines.append(f"        return {ret!r}")
            lines.append("")

        return "\n".join(lines) + "\n"
