"""Tests for lidco.codegen.template_v2."""
from __future__ import annotations

import pytest

from lidco.codegen.template_v2 import Template, TemplateEngineV2


class TestTemplate:
    """Tests for the Template dataclass."""

    def test_frozen(self) -> None:
        t = Template(name="t", language="py", body="hello")
        with pytest.raises(AttributeError):
            t.name = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        t = Template(name="t", language="py", body="")
        assert t.variables == []

    def test_with_variables(self) -> None:
        t = Template(name="t", language="py", body="", variables=["a", "b"])
        assert t.variables == ["a", "b"]


class TestTemplateEngineV2Register:
    """Tests for register / get / list_templates."""

    def test_register_and_get(self) -> None:
        engine = TemplateEngineV2()
        tpl = Template(name="greeting", language="py", body="Hello {{name}}")
        engine.register(tpl)
        assert engine.get("greeting") is tpl

    def test_get_missing(self) -> None:
        engine = TemplateEngineV2()
        assert engine.get("nope") is None

    def test_list_empty(self) -> None:
        engine = TemplateEngineV2()
        assert engine.list_templates() == []

    def test_list_sorted(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="z", language="py", body=""))
        engine.register(Template(name="a", language="py", body=""))
        names = [t.name for t in engine.list_templates()]
        assert names == ["a", "z"]

    def test_overwrite(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="old"))
        engine.register(Template(name="t", language="py", body="new"))
        assert engine.get("t").body == "new"  # type: ignore[union-attr]
        assert len(engine.list_templates()) == 1


class TestTemplateEngineV2Render:
    """Tests for render with variables, ifs, and fors."""

    def test_simple_variable(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="Hello {{name}}!"))
        assert engine.render("t", {"name": "World"}) == "Hello World!"

    def test_missing_variable_unchanged(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="{{missing}}"))
        assert engine.render("t", {}) == "{{missing}}"

    def test_multiple_variables(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="{{a}} and {{b}}"))
        assert engine.render("t", {"a": "X", "b": "Y"}) == "X and Y"

    def test_render_missing_template(self) -> None:
        engine = TemplateEngineV2()
        with pytest.raises(KeyError, match="Template not found"):
            engine.render("nope")

    def test_if_truthy(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="{% if show %}visible{% endif %}"))
        assert engine.render("t", {"show": True}) == "visible"

    def test_if_falsy(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="{% if show %}visible{% endif %}"))
        assert engine.render("t", {"show": False}) == ""

    def test_if_missing_key(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="{% if flag %}yes{% endif %}"))
        assert engine.render("t", {}) == ""

    def test_for_loop(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="{% for x in items %}{{x}},{% endfor %}"))
        assert engine.render("t", {"items": ["a", "b", "c"]}) == "a,b,c,"

    def test_for_empty_list(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="{% for x in items %}{{x}}{% endfor %}"))
        assert engine.render("t", {"items": []}) == ""

    def test_for_non_list(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="{% for x in items %}{{x}}{% endfor %}"))
        assert engine.render("t", {"items": "notalist"}) == ""

    def test_combined_if_for_vars(self) -> None:
        engine = TemplateEngineV2()
        body = "class {{name}}:{% if methods %}\n{% for m in methods %}    def {{m}}(self): pass\n{% endfor %}{% endif %}"
        engine.register(Template(name="t", language="py", body=body))
        result = engine.render("t", {"name": "Foo", "methods": ["bar", "baz"]})
        assert "class Foo:" in result
        assert "def bar(self): pass" in result
        assert "def baz(self): pass" in result

    def test_render_no_variables_arg(self) -> None:
        engine = TemplateEngineV2()
        engine.register(Template(name="t", language="py", body="plain"))
        assert engine.render("t") == "plain"
