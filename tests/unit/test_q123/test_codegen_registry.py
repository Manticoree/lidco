"""Tests for src/lidco/codegen/registry.py."""
from lidco.codegen.registry import CodegenRegistry, TemplateResult


class TestTemplateResult:
    def test_fields(self):
        r = TemplateResult(name="class", content="class Foo:", template_type="class")
        assert r.name == "class"
        assert r.content == "class Foo:"
        assert r.template_type == "class"


class TestCodegenRegistry:
    def test_init_empty(self):
        reg = CodegenRegistry()
        assert reg.list_templates() == []

    def test_register(self):
        reg = CodegenRegistry()
        reg.register("myfn", lambda: "output")
        assert "myfn" in reg.list_templates()

    def test_get_registered(self):
        reg = CodegenRegistry()
        fn = lambda: "x"
        reg.register("foo", fn)
        assert reg.get("foo") is fn

    def test_get_not_registered(self):
        reg = CodegenRegistry()
        assert reg.get("nonexistent") is None

    def test_list_templates_sorted(self):
        reg = CodegenRegistry()
        reg.register("z", lambda: "")
        reg.register("a", lambda: "")
        reg.register("m", lambda: "")
        assert reg.list_templates() == ["a", "m", "z"]

    def test_apply_registered(self):
        reg = CodegenRegistry()
        reg.register("greet", lambda name: f"Hello {name}")
        result = reg.apply("greet", name="World")
        assert isinstance(result, TemplateResult)
        assert result.content == "Hello World"
        assert result.name == "greet"

    def test_apply_not_registered_raises(self):
        reg = CodegenRegistry()
        try:
            reg.apply("missing_template_xyz")
            assert False, "Should have raised KeyError"
        except KeyError:
            pass

    def test_apply_template_type(self):
        reg = CodegenRegistry()
        reg.register("test_type", lambda: "content")
        result = reg.apply("test_type")
        assert result.template_type == "test_type"

    def test_with_defaults_has_class(self):
        reg = CodegenRegistry.with_defaults()
        assert "class" in reg.list_templates()

    def test_with_defaults_has_test(self):
        reg = CodegenRegistry.with_defaults()
        assert "test" in reg.list_templates()

    def test_with_defaults_has_module(self):
        reg = CodegenRegistry.with_defaults()
        assert "module" in reg.list_templates()

    def test_with_defaults_has_dataclass(self):
        reg = CodegenRegistry.with_defaults()
        assert "dataclass" in reg.list_templates()

    def test_with_defaults_has_abc(self):
        reg = CodegenRegistry.with_defaults()
        assert "abc" in reg.list_templates()

    def test_with_defaults_apply_class(self):
        reg = CodegenRegistry.with_defaults()
        result = reg.apply("class", name="MyClass")
        assert "class MyClass" in result.content

    def test_with_defaults_apply_module(self):
        reg = CodegenRegistry.with_defaults()
        result = reg.apply("module", name="my_module", description="Test module")
        assert isinstance(result.content, str)
        assert len(result.content) > 0

    def test_with_defaults_apply_test(self):
        reg = CodegenRegistry.with_defaults()
        result = reg.apply("test", module_name="mymod")
        assert "import pytest" in result.content or "mymod" in result.content

    def test_with_defaults_apply_dataclass(self):
        reg = CodegenRegistry.with_defaults()
        result = reg.apply("dataclass", name="Point", fields=[("x", "int")])
        assert "@dataclass" in result.content

    def test_with_defaults_apply_abc(self):
        reg = CodegenRegistry.with_defaults()
        result = reg.apply("abc", name="IBase")
        assert "ABC" in result.content or "abstract" in result.content.lower()

    def test_register_overwrites(self):
        reg = CodegenRegistry()
        reg.register("fn", lambda: "first")
        reg.register("fn", lambda: "second")
        result = reg.apply("fn")
        assert result.content == "second"
