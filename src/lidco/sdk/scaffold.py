"""Plugin Scaffold Generator — generate plugin project from template."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class ScaffoldError(Exception):
    """Raised for scaffold generation errors."""


@dataclass(frozen=True)
class ScaffoldConfig:
    """Configuration for plugin scaffold generation."""

    plugin_name: str
    author: str = ""
    version: str = "0.1.0"
    description: str = ""
    include_tests: bool = True
    include_readme: bool = True
    template: str = "default"


@dataclass(frozen=True)
class GeneratedFile:
    """A single generated file with its relative path and content."""

    path: str
    content: str


@dataclass(frozen=True)
class ScaffoldResult:
    """Result of scaffold generation."""

    files: tuple[GeneratedFile, ...]
    plugin_name: str
    root_dir: str


class PluginScaffoldGenerator:
    """Generate plugin project scaffolds from templates.

    Templates define the file structure and content for new plugin projects.
    The default template includes pyproject.toml, __init__.py, main.py,
    and optional test and README files.
    """

    _BUILTIN_TEMPLATES = ("default",)

    def __init__(self, templates_dir: str | Path | None = None) -> None:
        self._templates_dir = Path(templates_dir) if templates_dir else None

    # ---------------------------------------------------------------- public

    def generate(self, config: ScaffoldConfig) -> ScaffoldResult:
        """Generate scaffold files for a plugin project.

        Returns a ScaffoldResult with generated file contents (nothing written to disk).
        """
        if not config.plugin_name or not config.plugin_name.strip():
            raise ScaffoldError("Plugin name cannot be empty")

        name = config.plugin_name.strip()
        safe_name = name.replace("-", "_")
        root = safe_name

        if config.template not in self.list_templates():
            raise ScaffoldError(f"Unknown template: {config.template!r}")

        files: list[GeneratedFile] = []

        # pyproject.toml
        files.append(GeneratedFile(
            path=f"{root}/pyproject.toml",
            content=self._render_pyproject(name, safe_name, config),
        ))

        # package __init__.py
        files.append(GeneratedFile(
            path=f"{root}/{safe_name}/__init__.py",
            content=f'"""Plugin: {name}."""\n\n__version__ = "{config.version}"\n',
        ))

        # main.py
        files.append(GeneratedFile(
            path=f"{root}/{safe_name}/main.py",
            content=self._render_main(name, safe_name, config),
        ))

        # optional test
        if config.include_tests:
            files.append(GeneratedFile(
                path=f"{root}/tests/test_plugin.py",
                content=self._render_test(name, safe_name, config),
            ))

        # optional README
        if config.include_readme:
            files.append(GeneratedFile(
                path=f"{root}/README.md",
                content=self._render_readme(name, config),
            ))

        return ScaffoldResult(
            files=tuple(files),
            plugin_name=name,
            root_dir=root,
        )

    def write(self, result: ScaffoldResult, output_dir: str | Path) -> list[str]:
        """Write scaffold files to *output_dir*. Returns list of written paths."""
        base = Path(output_dir)
        written: list[str] = []
        for gf in result.files:
            target = base / gf.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(gf.content, encoding="utf-8")
            written.append(str(target))
        return written

    def list_templates(self) -> list[str]:
        """Return available template names."""
        templates = list(self._BUILTIN_TEMPLATES)
        if self._templates_dir and self._templates_dir.is_dir():
            for child in sorted(self._templates_dir.iterdir()):
                if child.is_dir() and child.name not in templates:
                    templates.append(child.name)
        return templates

    def preview(self, config: ScaffoldConfig) -> str:
        """Return a tree-view preview of what would be generated."""
        result = self.generate(config)
        lines = [f"{result.root_dir}/"]
        paths = sorted(gf.path for gf in result.files)
        for i, path in enumerate(paths):
            rel = path[len(result.root_dir) + 1:]  # strip root_dir/
            parts = rel.split("/")
            prefix = "  " * (len(parts) - 1)
            connector = "|-- " if i < len(paths) - 1 else "`-- "
            lines.append(f"{prefix}{connector}{parts[-1]}")
        return "\n".join(lines)

    # --------------------------------------------------------------- private

    def _render_pyproject(
        self, name: str, safe_name: str, config: ScaffoldConfig
    ) -> str:
        lines = [
            "[build-system]",
            'requires = ["setuptools>=68.0"]',
            'build-backend = "setuptools.backends._legacy:_Backend"',
            "",
            "[project]",
            f'name = "{name}"',
            f'version = "{config.version}"',
            f'description = "{config.description}"',
        ]
        if config.author:
            lines.append(f'authors = [{{name = "{config.author}"}}]')
        lines.extend([
            'requires-python = ">=3.11"',
            "",
            f"[project.entry-points.lidco_plugins]",
            f'{safe_name} = "{safe_name}.main:plugin_entry"',
            "",
        ])
        return "\n".join(lines)

    def _render_main(
        self, name: str, safe_name: str, config: ScaffoldConfig
    ) -> str:
        return (
            f'"""Main entry point for {name} plugin."""\n'
            f"\nfrom __future__ import annotations\n"
            f"\n\n"
            f"class {safe_name.title().replace('_', '')}Plugin:\n"
            f'    """Plugin implementation."""\n'
            f"\n"
            f"    def on_init(self) -> None:\n"
            f"        pass\n"
            f"\n"
            f"    def on_activate(self) -> None:\n"
            f"        pass\n"
            f"\n"
            f"    def on_deactivate(self) -> None:\n"
            f"        pass\n"
            f"\n"
            f"    def on_uninstall(self) -> None:\n"
            f"        pass\n"
            f"\n\n"
            f"def plugin_entry():\n"
            f'    """Entry point for plugin discovery."""\n'
            f"    return {safe_name.title().replace('_', '')}Plugin()\n"
        )

    def _render_test(
        self, name: str, safe_name: str, config: ScaffoldConfig
    ) -> str:
        cls = safe_name.title().replace("_", "")
        return (
            f'"""Tests for {name} plugin."""\n'
            f"\n"
            f"from {safe_name}.main import {cls}Plugin\n"
            f"\n\n"
            f"def test_plugin_init():\n"
            f"    plugin = {cls}Plugin()\n"
            f"    plugin.on_init()\n"
            f"\n\n"
            f"def test_plugin_activate():\n"
            f"    plugin = {cls}Plugin()\n"
            f"    plugin.on_activate()\n"
        )

    def _render_readme(self, name: str, config: ScaffoldConfig) -> str:
        lines = [f"# {name}", ""]
        if config.description:
            lines.append(config.description)
            lines.append("")
        lines.extend([
            "## Installation",
            "",
            f"```bash",
            f"pip install {name}",
            f"```",
            "",
        ])
        return "\n".join(lines)
