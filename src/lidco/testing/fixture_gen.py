"""Fixture Generator — generate pytest fixtures from Python class definitions (stdlib only).

Parses dataclasses, NamedTuples, and regular classes via AST and produces
ready-to-paste pytest fixture code with sensible default values.
"""
from __future__ import annotations

import ast
import textwrap
from dataclasses import dataclass, field
from typing import Any


class FixtureGenError(Exception):
    """Raised when fixture generation fails."""


# Default values used when we can't infer anything better
_TYPE_DEFAULTS: dict[str, str] = {
    "int": "0",
    "float": "0.0",
    "bool": "False",
    "str": '""',
    "bytes": 'b""',
    "list": "[]",
    "dict": "{}",
    "set": "set()",
    "tuple": "()",
    "List": "[]",
    "Dict": "{}",
    "Optional": "None",
    "Any": "None",
    "Path": 'Path(".")',
    "datetime": "datetime.now()",
    "date": "date.today()",
    "UUID": "uuid4()",
    "Decimal": "Decimal('0')",
}


@dataclass
class FieldDef:
    """A single field in a class definition."""

    name: str
    type_annotation: str = ""
    default: str = ""          # literal default from source
    has_default: bool = False

    def fixture_value(self) -> str:
        """Return a sensible fixture value for this field."""
        if self.has_default and self.default and self.default != "field()":
            return self.default
        # Look up by type
        base_type = self.type_annotation.split("[")[0].split("|")[0].strip()
        if base_type in _TYPE_DEFAULTS:
            return _TYPE_DEFAULTS[base_type]
        if "str" in base_type.lower():
            return f'"test_{self.name}"'
        if "int" in base_type.lower():
            return "1"
        if "float" in base_type.lower():
            return "1.0"
        if "bool" in base_type.lower():
            return "True"
        if "list" in base_type.lower() or base_type.endswith("[]"):
            return "[]"
        # Unknown type — use a sensible string
        return f'"test_{self.name}"'


@dataclass
class ClassDef:
    """Parsed class metadata."""

    name: str
    fields: list[FieldDef] = field(default_factory=list)
    is_dataclass: bool = False
    bases: list[str] = field(default_factory=list)
    lineno: int = 0


@dataclass
class GeneratedFixture:
    """A generated pytest fixture for a class."""

    class_name: str
    fixture_name: str
    code: str
    imports_needed: list[str] = field(default_factory=list)


class FixtureGenerator:
    """Parse Python source and generate pytest fixtures.

    Usage::

        gen = FixtureGenerator()
        source = '''
        @dataclass
        class User:
            name: str
            age: int
            email: str = ""
        '''
        fixtures = gen.generate(source)
        for f in fixtures:
            print(f.code)
    """

    def __init__(self, scope: str = "function") -> None:
        self._scope = scope  # pytest fixture scope

    # ------------------------------------------------------------------ #
    # Parsing                                                              #
    # ------------------------------------------------------------------ #

    def parse_classes(self, source: str) -> list[ClassDef]:
        """Extract class definitions from Python source."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise FixtureGenError(f"Syntax error: {exc}") from exc

        classes: list[ClassDef] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                cls_def = self._extract_class(node)
                classes.append(cls_def)
        return classes

    def _extract_class(self, node: ast.ClassDef) -> ClassDef:
        bases = [ast.unparse(b) for b in node.bases]
        is_dc = any(
            (isinstance(d, ast.Name) and d.id == "dataclass") or
            (isinstance(d, ast.Attribute) and d.attr == "dataclass")
            for d in node.decorator_list
        )

        fields: list[FieldDef] = []

        for item in node.body:
            # dataclass-style: name: type = default
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                name = item.target.id
                annotation = ast.unparse(item.annotation) if item.annotation else ""
                default = ""
                has_default = item.value is not None
                if has_default and item.value is not None:
                    default = ast.unparse(item.value)
                fields.append(FieldDef(
                    name=name,
                    type_annotation=annotation,
                    default=default,
                    has_default=has_default,
                ))

            # __init__ method — extract params as fields
            elif (
                isinstance(item, ast.FunctionDef)
                and item.name == "__init__"
                and not is_dc
            ):
                args = item.args
                n_args = len(args.args)
                n_defaults = len(args.defaults)
                defaults_start = n_args - n_defaults

                for i, arg in enumerate(args.args):
                    if arg.arg == "self":
                        continue
                    annotation = ast.unparse(arg.annotation) if arg.annotation else ""
                    has_default = i >= defaults_start
                    default = ""
                    if has_default:
                        default = ast.unparse(args.defaults[i - defaults_start])
                    fields.append(FieldDef(
                        name=arg.arg,
                        type_annotation=annotation,
                        default=default,
                        has_default=has_default,
                    ))

        return ClassDef(
            name=node.name,
            fields=fields,
            is_dataclass=is_dc,
            bases=bases,
            lineno=node.lineno,
        )

    # ------------------------------------------------------------------ #
    # Generation                                                           #
    # ------------------------------------------------------------------ #

    def generate(self, source: str) -> list[GeneratedFixture]:
        """Generate fixtures for all classes in source."""
        classes = self.parse_classes(source)
        return [self._generate_fixture(cls) for cls in classes]

    def generate_for_class(self, source: str, class_name: str) -> GeneratedFixture | None:
        """Generate fixture for a specific class."""
        classes = self.parse_classes(source)
        cls = next((c for c in classes if c.name == class_name), None)
        if cls is None:
            return None
        return self._generate_fixture(cls)

    def _generate_fixture(self, cls: ClassDef) -> GeneratedFixture:
        fixture_name = self._fixture_name(cls.name)
        scope_decorator = (
            f'@pytest.fixture(scope="{self._scope}")'
            if self._scope != "function"
            else "@pytest.fixture"
        )

        lines = [
            scope_decorator,
            f"def {fixture_name}():",
        ]

        if not cls.fields:
            lines.append(f"    return {cls.name}()")
        else:
            lines.append(f"    return {cls.name}(")
            for field_def in cls.fields:
                value = field_def.fixture_value()
                lines.append(f"        {field_def.name}={value},")
            lines.append("    )")

        code = "\n".join(lines)

        imports_needed = ["import pytest"]
        if any("Path" in f.type_annotation for f in cls.fields):
            imports_needed.append("from pathlib import Path")
        if any("datetime" in f.type_annotation for f in cls.fields):
            imports_needed.append("from datetime import datetime, date")
        if any("UUID" in f.type_annotation for f in cls.fields):
            imports_needed.append("from uuid import uuid4")
        if any("Decimal" in f.type_annotation for f in cls.fields):
            imports_needed.append("from decimal import Decimal")

        return GeneratedFixture(
            class_name=cls.name,
            fixture_name=fixture_name,
            code=code,
            imports_needed=imports_needed,
        )

    def generate_module(self, source: str) -> str:
        """Return a full test-fixtures module string for all classes in source."""
        fixtures = self.generate(source)
        if not fixtures:
            return "# No classes found to generate fixtures for\n"

        all_imports: list[str] = ["import pytest"]
        for f in fixtures:
            all_imports.extend(f.imports_needed)
        unique_imports = sorted(set(all_imports))

        parts = unique_imports + ["", ""]
        for fixture in fixtures:
            parts.append(fixture.code)
            parts.append("")
        return "\n".join(parts)

    @staticmethod
    def _fixture_name(class_name: str) -> str:
        """Convert ClassName to fixture_class_name."""
        # CamelCase → snake_case
        s = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
        return s


# Import re for fixture name helper
import re
