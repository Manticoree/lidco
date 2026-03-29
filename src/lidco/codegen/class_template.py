"""Class Template — generate Python class source code.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ClassConfig:
    """Configuration for class code generation."""
    name: str
    fields: list[tuple[str, str]] = field(default_factory=list)  # (field_name, field_type)
    base: str = ""
    is_dataclass: bool = False
    is_abc: bool = False
    docstring: str = ""


class ClassTemplate:
    """Generate Python class source code from ClassConfig."""

    def render(self, config: ClassConfig) -> str:
        """Generate a plain Python class."""
        lines: list[str] = []

        if config.is_abc:
            lines.append("from abc import ABC, abstractmethod")
            lines.append("")

        # Class declaration
        if config.base:
            lines.append(f"class {config.name}({config.base}):")
        elif config.is_abc:
            lines.append(f"class {config.name}(ABC):")
        else:
            lines.append(f"class {config.name}:")

        indent = "    "

        # Docstring
        if config.docstring:
            lines.append(f'{indent}"""{config.docstring}"""')
            lines.append("")

        # __init__ with fields
        if config.fields:
            params = ", ".join(f"{name}: {typ}" for name, typ in config.fields)
            lines.append(f"{indent}def __init__(self, {params}) -> None:")
            for name, _ in config.fields:
                lines.append(f"{indent}{indent}self.{name} = {name}")
        else:
            if not config.is_abc:
                lines.append(f"{indent}pass")

        return "\n".join(lines) + "\n"

    def render_dataclass(self, config: ClassConfig) -> str:
        """Generate a @dataclass class."""
        lines: list[str] = ["from dataclasses import dataclass", ""]
        lines.append("@dataclass")

        if config.base:
            lines.append(f"class {config.name}({config.base}):")
        else:
            lines.append(f"class {config.name}:")

        indent = "    "

        if config.docstring:
            lines.append(f'{indent}"""{config.docstring}"""')

        if config.fields:
            for name, typ in config.fields:
                lines.append(f"{indent}{name}: {typ}")
        else:
            lines.append(f"{indent}pass")

        return "\n".join(lines) + "\n"

    def render_abc(self, config: ClassConfig) -> str:
        """Generate an ABC class with abstract methods for each field as method stub."""
        lines: list[str] = ["from abc import ABC, abstractmethod", ""]

        if config.base:
            lines.append(f"class {config.name}({config.base}, ABC):")
        else:
            lines.append(f"class {config.name}(ABC):")

        indent = "    "

        if config.docstring:
            lines.append(f'{indent}"""{config.docstring}"""')
            lines.append("")

        if config.fields:
            for name, typ in config.fields:
                lines.append(f"{indent}@abstractmethod")
                lines.append(f"{indent}def {name}(self) -> {typ}:")
                lines.append(f"{indent}{indent}...")
                lines.append("")
        else:
            lines.append(f"{indent}pass")

        return "\n".join(lines) + "\n"
