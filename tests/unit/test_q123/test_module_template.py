"""Tests for src/lidco/codegen/module_template.py."""
from lidco.codegen.module_template import ModuleTemplate, ModuleConfig


class TestModuleConfig:
    def test_defaults(self):
        config = ModuleConfig(name="my_mod")
        assert config.name == "my_mod"
        assert config.description == ""
        assert config.imports == []
        assert config.exports == []
        assert config.docstring == ""

    def test_with_all_fields(self):
        config = ModuleConfig(
            name="mymod",
            description="My module",
            imports=["import os"],
            exports=["Foo", "Bar"],
            docstring="My module docstring.",
        )
        assert config.description == "My module"
        assert len(config.exports) == 2


class TestModuleTemplateRender:
    def test_render_returns_string(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="mymod")
        result = mt.render(config)
        assert isinstance(result, str)

    def test_render_with_docstring(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="mymod", docstring="My module.")
        result = mt.render(config)
        assert "My module." in result

    def test_render_with_description(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="mymod", description="A module for things.")
        result = mt.render(config)
        assert "A module for things." in result

    def test_render_with_imports(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="mymod", imports=["import os", "import sys"])
        result = mt.render(config)
        assert "import os" in result
        assert "import sys" in result

    def test_render_with_exports(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="mymod", exports=["Foo", "Bar"])
        result = mt.render(config)
        assert "__all__" in result
        assert "Foo" in result
        assert "Bar" in result

    def test_render_ends_with_newline(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="mymod")
        result = mt.render(config)
        assert result.endswith("\n")

    def test_render_empty_config(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="mymod")
        result = mt.render(config)
        assert len(result) > 0

    def test_render_no_docstring_uses_name(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="mymod")
        result = mt.render(config)
        assert "mymod" in result


class TestModuleTemplateRenderHeader:
    def test_render_header_with_docstring(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="x", docstring="My docs.")
        result = mt.render_header(config)
        assert "My docs." in result
        assert '"""' in result

    def test_render_header_with_description(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="x", description="Desc here.")
        result = mt.render_header(config)
        assert "Desc here." in result

    def test_render_header_returns_string(self):
        mt = ModuleTemplate()
        config = ModuleConfig(name="x")
        assert isinstance(mt.render_header(config), str)


class TestModuleTemplateRenderAll:
    def test_render_all_with_exports(self):
        mt = ModuleTemplate()
        result = mt.render_all(["Foo", "Bar"])
        assert "__all__" in result
        assert '"Foo"' in result
        assert '"Bar"' in result

    def test_render_all_empty(self):
        mt = ModuleTemplate()
        result = mt.render_all([])
        assert "__all__" in result

    def test_render_all_single(self):
        mt = ModuleTemplate()
        result = mt.render_all(["MyClass"])
        assert "MyClass" in result

    def test_render_all_returns_string(self):
        mt = ModuleTemplate()
        assert isinstance(mt.render_all(["x"]), str)

    def test_render_all_format(self):
        mt = ModuleTemplate()
        result = mt.render_all(["A", "B"])
        assert "=" in result
        assert "[" in result
        assert "]" in result
