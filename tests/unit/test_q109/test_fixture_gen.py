"""Tests for src/lidco/testing/fixture_gen.py."""
import pytest

from lidco.testing.fixture_gen import (
    ClassDef,
    FieldDef,
    FixtureGenError,
    FixtureGenerator,
    GeneratedFixture,
)

_DATACLASS_SOURCE = """\
from dataclasses import dataclass

@dataclass
class User:
    name: str
    age: int
    email: str = ""
    is_active: bool = True
"""

_REGULAR_CLASS = """\
class Product:
    def __init__(self, title: str, price: float, count: int = 0):
        self.title = title
        self.price = price
        self.count = count
"""

_EMPTY_CLASS = """\
class Empty:
    pass
"""

_MULTI_CLASS = """\
from dataclasses import dataclass

@dataclass
class Alpha:
    x: int

@dataclass
class Beta:
    y: str
"""


class TestFieldDef:
    def test_fixture_value_from_default_int(self):
        f = FieldDef(name="count", type_annotation="int", default="5", has_default=True)
        assert f.fixture_value() == "5"

    def test_fixture_value_from_type_str(self):
        f = FieldDef(name="name", type_annotation="str")
        assert '"' in f.fixture_value()

    def test_fixture_value_from_type_int(self):
        f = FieldDef(name="age", type_annotation="int")
        val = f.fixture_value()
        assert val in ("0", "1") or val.isdigit()

    def test_fixture_value_from_type_bool(self):
        f = FieldDef(name="flag", type_annotation="bool")
        assert f.fixture_value() in ("False", "True")

    def test_fixture_value_from_type_float(self):
        f = FieldDef(name="rate", type_annotation="float")
        v = f.fixture_value()
        assert "." in v or v.replace("-", "").isdigit()

    def test_fixture_value_from_type_list(self):
        f = FieldDef(name="items", type_annotation="list")
        assert f.fixture_value() == "[]"

    def test_fixture_value_unknown_type(self):
        f = FieldDef(name="custom", type_annotation="MyType")
        val = f.fixture_value()
        assert "custom" in val or val.startswith('"')


class TestFixtureGenerator:
    def test_parse_dataclass(self):
        gen = FixtureGenerator()
        classes = gen.parse_classes(_DATACLASS_SOURCE)
        assert any(c.name == "User" for c in classes)

    def test_parse_dataclass_fields(self):
        gen = FixtureGenerator()
        classes = gen.parse_classes(_DATACLASS_SOURCE)
        user = next(c for c in classes if c.name == "User")
        field_names = [f.name for f in user.fields]
        assert "name" in field_names
        assert "age" in field_names

    def test_parse_regular_class_init(self):
        gen = FixtureGenerator()
        classes = gen.parse_classes(_REGULAR_CLASS)
        product = next(c for c in classes if c.name == "Product")
        field_names = [f.name for f in product.fields]
        assert "title" in field_names
        assert "price" in field_names

    def test_parse_empty_class(self):
        gen = FixtureGenerator()
        classes = gen.parse_classes(_EMPTY_CLASS)
        empty = next(c for c in classes if c.name == "Empty")
        assert empty.fields == []

    def test_parse_syntax_error_raises(self):
        gen = FixtureGenerator()
        with pytest.raises(FixtureGenError):
            gen.parse_classes("def (broken")

    def test_generate_returns_list(self):
        gen = FixtureGenerator()
        fixtures = gen.generate(_DATACLASS_SOURCE)
        assert isinstance(fixtures, list)

    def test_generate_fixture_name(self):
        gen = FixtureGenerator()
        fixtures = gen.generate(_DATACLASS_SOURCE)
        user_fixture = next(f for f in fixtures if f.class_name == "User")
        assert user_fixture.fixture_name == "user"

    def test_generate_code_has_pytest_fixture(self):
        gen = FixtureGenerator()
        fixtures = gen.generate(_DATACLASS_SOURCE)
        user = next(f for f in fixtures if f.class_name == "User")
        assert "@pytest.fixture" in user.code

    def test_generate_code_has_class_name(self):
        gen = FixtureGenerator()
        fixtures = gen.generate(_DATACLASS_SOURCE)
        user = next(f for f in fixtures if f.class_name == "User")
        assert "User(" in user.code

    def test_generate_code_has_field_values(self):
        gen = FixtureGenerator()
        fixtures = gen.generate(_DATACLASS_SOURCE)
        user = next(f for f in fixtures if f.class_name == "User")
        assert "name=" in user.code or "age=" in user.code

    def test_generate_for_class_found(self):
        gen = FixtureGenerator()
        fixture = gen.generate_for_class(_DATACLASS_SOURCE, "User")
        assert fixture is not None
        assert fixture.class_name == "User"

    def test_generate_for_class_not_found(self):
        gen = FixtureGenerator()
        fixture = gen.generate_for_class(_DATACLASS_SOURCE, "Ghost")
        assert fixture is None

    def test_generate_multi_class(self):
        gen = FixtureGenerator()
        fixtures = gen.generate(_MULTI_CLASS)
        names = [f.class_name for f in fixtures]
        assert "Alpha" in names
        assert "Beta" in names

    def test_generate_module_has_imports(self):
        gen = FixtureGenerator()
        module = gen.generate_module(_DATACLASS_SOURCE)
        assert "import pytest" in module

    def test_generate_module_empty_source(self):
        gen = FixtureGenerator()
        module = gen.generate_module("x = 1\n")
        assert "No classes found" in module

    def test_scope_session(self):
        gen = FixtureGenerator(scope="session")
        fixtures = gen.generate(_DATACLASS_SOURCE)
        user = next(f for f in fixtures if f.class_name == "User")
        assert "session" in user.code

    def test_fixture_name_camel_case(self):
        assert FixtureGenerator._fixture_name("MyClass") == "my_class"
        assert FixtureGenerator._fixture_name("User") == "user"
        assert FixtureGenerator._fixture_name("HTTPClient") == "h_t_t_p_client"

    def test_dataclass_flag(self):
        gen = FixtureGenerator()
        classes = gen.parse_classes(_DATACLASS_SOURCE)
        user = next(c for c in classes if c.name == "User")
        assert user.is_dataclass is True

    def test_imports_needed_basic(self):
        gen = FixtureGenerator()
        fixtures = gen.generate(_DATACLASS_SOURCE)
        user = next(f for f in fixtures if f.class_name == "User")
        assert "import pytest" in user.imports_needed
