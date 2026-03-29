"""Tests for src/lidco/codegen/test_template.py."""
from lidco.codegen.test_template import TestTemplate, TestConfig


class TestTestConfig:
    def test_defaults(self):
        config = TestConfig(module_name="mymod")
        assert config.module_name == "mymod"
        assert config.class_names == []
        assert config.methods == []
        assert config.import_path == ""

    def test_with_classes(self):
        config = TestConfig(module_name="m", class_names=["Foo", "Bar"])
        assert "Foo" in config.class_names


class TestTestTemplateRender:
    def test_render_docstring(self):
        tt = TestTemplate()
        config = TestConfig(module_name="mymod")
        result = tt.render(config)
        assert "mymod" in result

    def test_render_pytest_import(self):
        tt = TestTemplate()
        config = TestConfig(module_name="mymod")
        result = tt.render(config)
        assert "import pytest" in result

    def test_render_with_class_names(self):
        tt = TestTemplate()
        config = TestConfig(module_name="mymod", class_names=["MyClass"])
        result = tt.render(config)
        assert "TestMyClass" in result or "MyClass" in result

    def test_render_with_methods(self):
        tt = TestTemplate()
        config = TestConfig(module_name="mymod", class_names=["Foo"], methods=["init", "run"])
        result = tt.render(config)
        assert "test_init" in result or "init" in result

    def test_render_import_path(self):
        tt = TestTemplate()
        config = TestConfig(
            module_name="mymod",
            class_names=["Foo"],
            import_path="lidco.mymod",
        )
        result = tt.render(config)
        assert "lidco.mymod" in result

    def test_render_returns_string(self):
        tt = TestTemplate()
        config = TestConfig(module_name="x")
        assert isinstance(tt.render(config), str)

    def test_render_empty_config(self):
        tt = TestTemplate()
        config = TestConfig(module_name="empty")
        result = tt.render(config)
        assert isinstance(result, str)
        assert len(result) > 0


class TestTestTemplateRenderClass:
    def test_render_class_name(self):
        tt = TestTemplate()
        result = tt.render_class("MyClass", [])
        assert "TestMyClass" in result or "MyClass" in result

    def test_render_class_with_methods(self):
        tt = TestTemplate()
        result = tt.render_class("Foo", ["init", "compute"])
        assert "test_init" in result or "init" in result

    def test_render_class_returns_string(self):
        tt = TestTemplate()
        assert isinstance(tt.render_class("X", []), str)

    def test_render_class_no_methods_has_default_test(self):
        tt = TestTemplate()
        result = tt.render_class("Bar", [])
        assert "def test_" in result

    def test_render_class_multiple_methods(self):
        tt = TestTemplate()
        result = tt.render_class("Widget", ["create", "delete", "update"])
        assert "create" in result or "test_create" in result


class TestTestTemplateRenderMethodStub:
    def test_render_method_stub_name(self):
        tt = TestTemplate()
        result = tt.render_method_stub("my_method")
        assert "test_my_method" in result

    def test_render_method_stub_already_test(self):
        tt = TestTemplate()
        result = tt.render_method_stub("test_already")
        assert "test_already" in result

    def test_render_method_stub_has_def(self):
        tt = TestTemplate()
        result = tt.render_method_stub("foo")
        assert "def " in result

    def test_render_method_stub_has_pass(self):
        tt = TestTemplate()
        result = tt.render_method_stub("foo")
        assert "pass" in result or "TODO" in result

    def test_render_method_stub_returns_string(self):
        tt = TestTemplate()
        assert isinstance(tt.render_method_stub("x"), str)
