"""Tests for lidco.codegen.crud."""
from __future__ import annotations

import pytest

from lidco.codegen.crud import CRUDGenerator, ModelDef


class TestModelDef:
    """Tests for the ModelDef dataclass."""

    def test_frozen(self) -> None:
        m = ModelDef(name="User", fields=[])
        with pytest.raises(AttributeError):
            m.name = "Other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        m = ModelDef(name="User")
        assert m.fields == []


class TestCRUDGeneratorGenerateModel:
    """Tests for generate_model."""

    def test_basic_model(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(name="User", fields=[{"name": "email", "type": "str"}])
        code = gen.generate_model(model)
        assert "class User:" in code
        assert "email: str" in code
        assert "from __future__ import annotations" in code

    def test_empty_fields(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(name="Empty", fields=[])
        code = gen.generate_model(model)
        assert "pass" in code

    def test_multiple_fields(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(
            name="Product",
            fields=[{"name": "title", "type": "str"}, {"name": "price", "type": "float"}],
        )
        code = gen.generate_model(model)
        assert "title: str" in code
        assert "price: float" in code

    def test_frozen_dataclass(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(name="T", fields=[])
        code = gen.generate_model(model)
        assert "@dataclass(frozen=True)" in code


class TestCRUDGeneratorGenerateRoutes:
    """Tests for generate_routes."""

    def test_routes_generated(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(name="User", fields=[{"name": "email", "type": "str"}])
        code = gen.generate_routes(model)
        assert "def list_users()" in code
        assert "def get_user(" in code
        assert "def create_user(" in code
        assert "def delete_user(" in code

    def test_routes_empty_fields(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(name="Item", fields=[])
        code = gen.generate_routes(model)
        assert "def list_items()" in code


class TestCRUDGeneratorGenerateTests:
    """Tests for generate_tests."""

    def test_tests_generated(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(name="User", fields=[{"name": "email", "type": "str"}])
        code = gen.generate_tests(model)
        assert "def test_create_user()" in code
        assert "def test_list_users()" in code
        assert "def test_delete_user()" in code


class TestCRUDGeneratorGenerate:
    """Tests for the top-level generate method."""

    def test_generate_returns_dict(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(name="Order", fields=[{"name": "total", "type": "float"}])
        result = gen.generate(model)
        assert isinstance(result, dict)
        assert len(result) == 3

    def test_generate_keys(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(name="Order", fields=[])
        result = gen.generate(model)
        assert "order/model.py" in result
        assert "order/routes.py" in result
        assert "tests/test_order.py" in result

    def test_generate_with_style(self) -> None:
        gen = CRUDGenerator()
        model = ModelDef(name="Item", fields=[])
        result = gen.generate(model, style="rest")
        assert len(result) == 3
