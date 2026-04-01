"""Tests for lidco.sdk.scaffold — PluginScaffoldGenerator."""

from pathlib import Path

from lidco.sdk.scaffold import (
    GeneratedFile,
    PluginScaffoldGenerator,
    ScaffoldConfig,
    ScaffoldError,
    ScaffoldResult,
)


def _gen() -> PluginScaffoldGenerator:
    return PluginScaffoldGenerator()


def test_generate_default():
    gen = _gen()
    config = ScaffoldConfig(plugin_name="my-plugin", author="Alice", description="A cool plugin")
    result = gen.generate(config)
    assert isinstance(result, ScaffoldResult)
    assert result.plugin_name == "my-plugin"
    assert result.root_dir == "my_plugin"
    paths = [f.path for f in result.files]
    assert any("pyproject.toml" in p for p in paths)
    assert any("__init__.py" in p for p in paths)
    assert any("main.py" in p for p in paths)
    assert any("test_plugin.py" in p for p in paths)
    assert any("README.md" in p for p in paths)


def test_generate_without_tests():
    gen = _gen()
    config = ScaffoldConfig(plugin_name="notests", include_tests=False)
    result = gen.generate(config)
    paths = [f.path for f in result.files]
    assert not any("test_plugin" in p for p in paths)


def test_generate_without_readme():
    gen = _gen()
    config = ScaffoldConfig(plugin_name="noreadme", include_readme=False)
    result = gen.generate(config)
    paths = [f.path for f in result.files]
    assert not any("README" in p for p in paths)


def test_generate_empty_name_raises():
    gen = _gen()
    config = ScaffoldConfig(plugin_name="")
    try:
        gen.generate(config)
        assert False, "Expected ScaffoldError"
    except ScaffoldError:
        pass


def test_preview():
    gen = _gen()
    config = ScaffoldConfig(plugin_name="preview-plugin")
    preview = gen.preview(config)
    assert "preview_plugin/" in preview
    assert "pyproject.toml" in preview
    assert "main.py" in preview


def test_write_to_disk(tmp_path):
    gen = _gen()
    config = ScaffoldConfig(plugin_name="disk-test", author="Bob")
    result = gen.generate(config)
    written = gen.write(result, tmp_path)
    assert len(written) == len(result.files)
    for path_str in written:
        assert Path(path_str).exists()
    # Check pyproject.toml content
    pyproject = tmp_path / "disk_test" / "pyproject.toml"
    assert pyproject.exists()
    content = pyproject.read_text(encoding="utf-8")
    assert 'name = "disk-test"' in content
    assert "Bob" in content


def test_list_templates():
    gen = _gen()
    templates = gen.list_templates()
    assert "default" in templates


def test_list_templates_with_custom_dir(tmp_path):
    custom_dir = tmp_path / "templates"
    custom_dir.mkdir()
    (custom_dir / "my_template").mkdir()
    gen = PluginScaffoldGenerator(templates_dir=custom_dir)
    templates = gen.list_templates()
    assert "default" in templates
    assert "my_template" in templates


def test_unknown_template_raises():
    gen = _gen()
    config = ScaffoldConfig(plugin_name="x", template="nonexistent")
    try:
        gen.generate(config)
        assert False, "Expected ScaffoldError"
    except ScaffoldError as exc:
        assert "nonexistent" in str(exc)


def test_generated_file_content():
    gen = _gen()
    config = ScaffoldConfig(plugin_name="content-check", version="2.0.0")
    result = gen.generate(config)
    init_file = next(f for f in result.files if "__init__.py" in f.path)
    assert '2.0.0' in init_file.content
