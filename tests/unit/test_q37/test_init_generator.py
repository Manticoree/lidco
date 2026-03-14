"""Tests for InitGenerator — Q37 task 251."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lidco.cli.init_generator import InitGenerator


class TestInitGeneratorPython:
    def test_detects_python(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\naddopts = "-q"\n[tool.ruff]\n', encoding="utf-8"
        )
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        assert profile.language == "Python"

    def test_detects_pytest(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\n', encoding="utf-8"
        )
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        assert profile.test_runner == "pytest"
        assert "pytest" in profile.test_command

    def test_detects_ruff(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.ruff]\nselect = ["E"]\n', encoding="utf-8"
        )
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        assert any("ruff" in l for l in profile.linters)

    def test_detects_mypy(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.mypy]\nstrict = true\n', encoding="utf-8"
        )
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        assert any("mypy" in l for l in profile.linters)

    def test_detects_fastapi_framework(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            'dependencies = ["fastapi>=0.100"]\n', encoding="utf-8"
        )
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        assert profile.framework == "Fastapi"


class TestInitGeneratorNode:
    def test_detects_node(self, tmp_path: Path) -> None:
        pkg = {"name": "my-app", "scripts": {"test": "jest"}, "devDependencies": {"jest": "^29"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        assert "Node" in profile.language

    def test_detects_jest(self, tmp_path: Path) -> None:
        pkg = {"devDependencies": {"jest": "^29"}, "scripts": {"test": "jest"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        assert profile.test_runner == "jest"

    def test_detects_pnpm(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        assert any("pnpm" in c for c in profile.conventions)


class TestInitGeneratorGenerate:
    def test_generate_contains_language(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n", encoding="utf-8")
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        content = gen.generate(profile)
        assert "Python" in content

    def test_generate_contains_test_command(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        content = gen.generate(profile)
        assert "pytest" in content

    def test_generate_contains_required_sections(self, tmp_path: Path) -> None:
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        content = gen.generate(profile)
        for section in ("## Project", "## Commands", "## Conventions", "## Testing", "## Safety"):
            assert section in content

    def test_generate_unknown_project(self, tmp_path: Path) -> None:
        gen = InitGenerator(tmp_path)
        profile = gen.analyze()
        content = gen.generate(profile)
        assert "LIDCO.md" in content  # at least the header is there
