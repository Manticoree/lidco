"""Tests for lidco.codegen.scaffold."""
from __future__ import annotations

import pytest

from lidco.codegen.scaffold import ScaffoldGenerator, ScaffoldSpec


class TestScaffoldSpec:
    """Tests for the ScaffoldSpec dataclass."""

    def test_frozen(self) -> None:
        spec = ScaffoldSpec(name="proj", type="api")
        with pytest.raises(AttributeError):
            spec.name = "other"  # type: ignore[misc]

    def test_defaults(self) -> None:
        spec = ScaffoldSpec(name="proj", type="cli")
        assert spec.files == []


class TestScaffoldGeneratorFromType:
    """Tests for from_type presets."""

    def test_api_preset(self) -> None:
        gen = ScaffoldGenerator()
        spec = gen.from_type("api", "myapi")
        assert spec.type == "api"
        assert spec.name == "myapi"
        assert len(spec.files) > 0

    def test_cli_preset(self) -> None:
        gen = ScaffoldGenerator()
        spec = gen.from_type("cli", "mycli")
        assert spec.type == "cli"
        assert any("{name}" in f.get("path", "") or "mycli" in f.get("path", "") for f in spec.files)

    def test_library_preset(self) -> None:
        gen = ScaffoldGenerator()
        spec = gen.from_type("library", "mylib")
        assert spec.type == "library"
        assert len(spec.files) > 0

    def test_unknown_type_raises(self) -> None:
        gen = ScaffoldGenerator()
        with pytest.raises(ValueError, match="Unknown project type"):
            gen.from_type("unknown", "proj")


class TestScaffoldGeneratorGenerate:
    """Tests for generate."""

    def test_generate_api(self) -> None:
        gen = ScaffoldGenerator()
        spec = gen.from_type("api", "myapi")
        files = gen.generate(spec)
        assert isinstance(files, dict)
        assert "app/main.py" in files
        assert "tests/test_main.py" in files

    def test_generate_cli_replaces_name(self) -> None:
        gen = ScaffoldGenerator()
        spec = gen.from_type("cli", "hello")
        files = gen.generate(spec)
        assert "hello/cli.py" in files
        assert "Hello from hello" in files["hello/cli.py"]

    def test_generate_library_replaces_name(self) -> None:
        gen = ScaffoldGenerator()
        spec = gen.from_type("library", "mylib")
        files = gen.generate(spec)
        assert "src/mylib/__init__.py" in files

    def test_generate_empty_spec(self) -> None:
        gen = ScaffoldGenerator()
        spec = ScaffoldSpec(name="empty", type="custom", files=[])
        files = gen.generate(spec)
        assert files == {}

    def test_generate_custom_spec(self) -> None:
        gen = ScaffoldGenerator()
        spec = ScaffoldSpec(
            name="proj",
            type="custom",
            files=[{"path": "{name}/main.py", "content": "# {name}"}],
        )
        files = gen.generate(spec)
        assert "proj/main.py" in files
        assert files["proj/main.py"] == "# proj"


class TestScaffoldGeneratorPreview:
    """Tests for preview."""

    def test_preview_api(self) -> None:
        gen = ScaffoldGenerator()
        spec = gen.from_type("api", "demo")
        preview = gen.preview(spec)
        assert "demo/" in preview
        assert "main.py" in preview

    def test_preview_empty(self) -> None:
        gen = ScaffoldGenerator()
        spec = ScaffoldSpec(name="e", type="custom", files=[])
        assert gen.preview(spec) == "(empty scaffold)"
