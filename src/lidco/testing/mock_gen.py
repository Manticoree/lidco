"""Mock Generator — generate unittest.mock setup code from class definitions (stdlib only).

Given a Python class, generates ready-to-paste mock setup code:
- MagicMock with spec for type-safe mocking
- Attribute/method stubs with return_value, side_effect
- Patch decorators for test functions
- Async mock variants for async methods
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any


class MockGenError(Exception):
    """Raised when mock generation fails."""


@dataclass
class MethodStub:
    """A single method mock configuration."""

    name: str
    is_async: bool = False
    return_type: str = ""
    params: list[str] = field(default_factory=list)

    def mock_attr(self) -> str:
        """Return the mock attribute name."""
        return f"mock_{self.name}" if self.name != "__init__" else ""

    def mock_setup(self, mock_var: str = "mock") -> str:
        """Return a mock setup line."""
        if self.name == "__init__":
            return ""
        attr = f"{mock_var}.{self.name}"
        if self.is_async:
            return f"{attr} = AsyncMock(return_value=None)"
        return_val = self._default_return()
        return f"{attr}.return_value = {return_val}"

    def _default_return(self) -> str:
        typ = self.return_type.strip()
        if not typ or typ == "None":
            return "None"
        if typ == "str":
            return '"mock_value"'
        if typ in ("int", "float"):
            return "0"
        if typ == "bool":
            return "True"
        if "list" in typ.lower() or typ.endswith("]") and "List" in typ:
            return "[]"
        if "dict" in typ.lower() or "Dict" in typ:
            return "{}"
        return "MagicMock()"


@dataclass
class ClassMockSpec:
    """Mock specification for a class."""

    class_name: str
    module_path: str = ""
    methods: list[MethodStub] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)

    def mock_var(self) -> str:
        return f"mock_{self.class_name.lower()}"

    def public_methods(self) -> list[MethodStub]:
        return [m for m in self.methods if not m.name.startswith("_") or m.name == "__init__"]

    def async_methods(self) -> list[MethodStub]:
        return [m for m in self.methods if m.is_async]


@dataclass
class GeneratedMock:
    """Generated mock code for a class."""

    class_name: str
    mock_var: str
    setup_code: str
    patch_decorator: str
    fixture_code: str
    imports: list[str] = field(default_factory=list)


class MockGenerator:
    """Parse Python source and generate unittest.mock code.

    Usage::

        gen = MockGenerator()
        source = '''
        class UserService:
            def get_user(self, user_id: int) -> dict:
                ...
            async def fetch_data(self) -> list:
                ...
        '''
        mocks = gen.generate(source)
        for m in mocks:
            print(m.setup_code)
    """

    def __init__(self, module_path: str = "") -> None:
        self._module_path = module_path

    # ------------------------------------------------------------------ #
    # Parsing                                                              #
    # ------------------------------------------------------------------ #

    def parse_classes(self, source: str) -> list[ClassMockSpec]:
        """Extract class mock specs from Python source."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            raise MockGenError(f"Syntax error: {exc}") from exc

        specs: list[ClassMockSpec] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                specs.append(self._extract_spec(node))
        return specs

    def _extract_spec(self, node: ast.ClassDef) -> ClassMockSpec:
        methods: list[MethodStub] = []
        attributes: list[str] = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stub = self._extract_method(item)
                methods.append(stub)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                attributes.append(item.target.id)

        return ClassMockSpec(
            class_name=node.name,
            module_path=self._module_path,
            methods=methods,
            attributes=attributes,
        )

    def _extract_method(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> MethodStub:
        params = [
            arg.arg for arg in node.args.args if arg.arg not in ("self", "cls")
        ]
        return_type = ast.unparse(node.returns) if node.returns else ""
        return MethodStub(
            name=node.name,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            return_type=return_type,
            params=params,
        )

    # ------------------------------------------------------------------ #
    # Generation                                                           #
    # ------------------------------------------------------------------ #

    def generate(self, source: str) -> list[GeneratedMock]:
        specs = self.parse_classes(source)
        return [self._generate_mock(spec) for spec in specs]

    def generate_for_class(self, source: str, class_name: str) -> GeneratedMock | None:
        specs = self.parse_classes(source)
        spec = next((s for s in specs if s.class_name == class_name), None)
        if spec is None:
            return None
        return self._generate_mock(spec)

    def _generate_mock(self, spec: ClassMockSpec) -> GeneratedMock:
        mock_var = spec.mock_var()
        has_async = bool(spec.async_methods())

        imports = ["from unittest.mock import MagicMock, patch"]
        if has_async:
            imports[0] = "from unittest.mock import MagicMock, AsyncMock, patch"

        # Simple setup block
        lines = [f"{mock_var} = MagicMock(spec={spec.class_name})"]
        for method in spec.methods:
            setup = method.mock_setup(mock_var)
            if setup:
                lines.append(setup)
        for attr in spec.attributes:
            lines.append(f"{mock_var}.{attr} = MagicMock()")
        setup_code = "\n".join(lines)

        # Patch decorator
        if spec.module_path:
            target = f"{spec.module_path}.{spec.class_name}"
        else:
            target = spec.class_name
        patch_decorator = f'@patch("{target}")'

        # Pytest fixture
        fixture_lines = [
            "import pytest",
            "from unittest.mock import MagicMock" + (", AsyncMock" if has_async else ""),
            "",
            "@pytest.fixture",
            f"def {mock_var}():",
            f"    mock = MagicMock(spec={spec.class_name})",
        ]
        for method in spec.methods:
            if method.name == "__init__":
                continue
            attr = f"mock.{method.name}"
            if method.is_async:
                fixture_lines.append(f"    {attr} = AsyncMock(return_value=None)")
            else:
                ret = method._default_return()
                fixture_lines.append(f"    {attr}.return_value = {ret}")
        fixture_lines.append("    return mock")
        fixture_code = "\n".join(fixture_lines)

        return GeneratedMock(
            class_name=spec.class_name,
            mock_var=mock_var,
            setup_code=setup_code,
            patch_decorator=patch_decorator,
            fixture_code=fixture_code,
            imports=imports,
        )

    def generate_patch_test(self, source: str, class_name: str) -> str:
        """Generate a complete test function using patch."""
        mock = self.generate_for_class(source, class_name)
        if not mock:
            return f"# Class {class_name!r} not found"
        lines = [
            mock.imports[0],
            "",
            mock.patch_decorator,
            f"def test_{mock.mock_var}(mock_cls):",
            f"    {mock.mock_var} = mock_cls.return_value",
        ]
        for method in self.parse_classes(source):
            if method.class_name != class_name:
                continue
            for m in method.methods:
                if m.name.startswith("_"):
                    continue
                lines.append(f"    {mock.mock_var}.{m.name}.assert_not_called()")
        lines.append("    # TODO: add assertions")
        return "\n".join(lines)
