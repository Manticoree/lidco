"""Tests for src/lidco/codegen/class_template.py."""
from lidco.codegen.class_template import ClassTemplate, ClassConfig


class TestClassConfig:
    def test_defaults(self):
        config = ClassConfig(name="Foo")
        assert config.name == "Foo"
        assert config.fields == []
        assert config.base == ""
        assert config.is_dataclass is False
        assert config.is_abc is False
        assert config.docstring == ""

    def test_with_fields(self):
        config = ClassConfig(name="Bar", fields=[("x", "int"), ("y", "str")])
        assert len(config.fields) == 2

    def test_with_base(self):
        config = ClassConfig(name="Sub", base="Base")
        assert config.base == "Base"


class TestClassTemplateRender:
    def test_render_simple(self):
        ct = ClassTemplate()
        config = ClassConfig(name="MyClass")
        result = ct.render(config)
        assert "class MyClass" in result

    def test_render_with_fields(self):
        ct = ClassTemplate()
        config = ClassConfig(name="Point", fields=[("x", "float"), ("y", "float")])
        result = ct.render(config)
        assert "self.x = x" in result
        assert "self.y = y" in result

    def test_render_with_base(self):
        ct = ClassTemplate()
        config = ClassConfig(name="Child", base="Parent")
        result = ct.render(config)
        assert "class Child(Parent)" in result

    def test_render_with_docstring(self):
        ct = ClassTemplate()
        config = ClassConfig(name="Doc", docstring="My docstring.")
        result = ct.render(config)
        assert "My docstring." in result

    def test_render_no_fields_has_pass_or_init(self):
        ct = ClassTemplate()
        config = ClassConfig(name="Empty")
        result = ct.render(config)
        assert "pass" in result or "def __init__" in result

    def test_render_returns_string(self):
        ct = ClassTemplate()
        config = ClassConfig(name="X")
        assert isinstance(ct.render(config), str)

    def test_render_init_signature(self):
        ct = ClassTemplate()
        config = ClassConfig(name="Foo", fields=[("name", "str")])
        result = ct.render(config)
        assert "def __init__" in result
        assert "name: str" in result


class TestClassTemplateRenderDataclass:
    def test_render_dataclass_decorator(self):
        ct = ClassTemplate()
        config = ClassConfig(name="Point", fields=[("x", "int"), ("y", "int")])
        result = ct.render_dataclass(config)
        assert "@dataclass" in result

    def test_render_dataclass_import(self):
        ct = ClassTemplate()
        config = ClassConfig(name="Point")
        result = ct.render_dataclass(config)
        assert "from dataclasses import dataclass" in result

    def test_render_dataclass_fields_typed(self):
        ct = ClassTemplate()
        config = ClassConfig(name="Data", fields=[("value", "str"), ("count", "int")])
        result = ct.render_dataclass(config)
        assert "value: str" in result
        assert "count: int" in result

    def test_render_dataclass_class_name(self):
        ct = ClassTemplate()
        config = ClassConfig(name="MyData")
        result = ct.render_dataclass(config)
        assert "class MyData" in result

    def test_render_dataclass_no_fields(self):
        ct = ClassTemplate()
        config = ClassConfig(name="Empty")
        result = ct.render_dataclass(config)
        assert "pass" in result or "class Empty" in result


class TestClassTemplateRenderAbc:
    def test_render_abc_import(self):
        ct = ClassTemplate()
        config = ClassConfig(name="IBase")
        result = ct.render_abc(config)
        assert "ABC" in result or "abstractmethod" in result

    def test_render_abc_class(self):
        ct = ClassTemplate()
        config = ClassConfig(name="IBase")
        result = ct.render_abc(config)
        assert "class IBase" in result

    def test_render_abc_abstract_methods(self):
        ct = ClassTemplate()
        config = ClassConfig(name="IFoo", fields=[("compute", "int"), ("name", "str")])
        result = ct.render_abc(config)
        assert "@abstractmethod" in result

    def test_render_abc_returns_string(self):
        ct = ClassTemplate()
        config = ClassConfig(name="X")
        assert isinstance(ct.render_abc(config), str)
