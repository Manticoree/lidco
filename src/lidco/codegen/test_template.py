"""Test Template — generate pytest test file stubs.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TestConfig:
    """Configuration for test file generation."""
    module_name: str
    class_names: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    import_path: str = ""


class TestTemplate:
    """Generate pytest test files from TestConfig."""

    def render(self, config: TestConfig) -> str:
        """Generate a full pytest test file."""
        lines: list[str] = []

        # Header
        lines.append(f'"""Tests for {config.module_name}."""')
        lines.append("import pytest")

        if config.import_path:
            lines.append(f"from {config.import_path} import {', '.join(config.class_names) if config.class_names else config.module_name}")

        lines.append("")

        if config.class_names:
            for class_name in config.class_names:
                lines.append(self.render_class(class_name, config.methods))
                lines.append("")
        elif config.methods:
            for method in config.methods:
                lines.append(self.render_method_stub(method))
                lines.append("")

        return "\n".join(lines)

    def render_class(self, class_name: str, methods: list[str]) -> str:
        """Generate a TestXxx class with method stubs."""
        lines: list[str] = [f"class Test{class_name}:"]
        indent = "    "

        if methods:
            for method in methods:
                stub = self.render_method_stub(method)
                # Indent the stub
                for stub_line in stub.splitlines():
                    lines.append(f"{indent}{stub_line}")
                lines.append("")
        else:
            lines.append(f"{indent}def test_instantiation(self):")
            lines.append(f"{indent}    obj = {class_name}()")
            lines.append(f"{indent}    assert obj is not None")

        return "\n".join(lines)

    def render_method_stub(self, method_name: str) -> str:
        """Generate a single test method stub."""
        test_name = f"test_{method_name}" if not method_name.startswith("test_") else method_name
        lines = [
            f"def {test_name}():",
            "    # TODO: implement test",
            "    pass",
        ]
        return "\n".join(lines)
