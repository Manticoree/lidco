"""Project templates for onboarding — task 1104."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.onboarding.detector import ProjectType


@dataclass(frozen=True)
class ProjectTemplate:
    """A project scaffold template."""

    name: str
    project_type: ProjectType
    files: tuple[tuple[str, str], ...]
    description: str


class TemplateLibrary:
    """Immutable collection of project templates."""

    def __init__(self, templates: tuple[ProjectTemplate, ...] = ()) -> None:
        self._templates = templates

    def register(self, template: ProjectTemplate) -> "TemplateLibrary":
        """Return a new library with *template* added."""
        filtered = tuple(t for t in self._templates if t.name != template.name)
        return TemplateLibrary((*filtered, template))

    def get(self, name: str) -> ProjectTemplate | None:
        """Return template by name or *None*."""
        for t in self._templates:
            if t.name == name:
                return t
        return None

    def list_for_type(self, project_type: ProjectType) -> tuple[ProjectTemplate, ...]:
        """Return all templates matching *project_type*."""
        return tuple(t for t in self._templates if t.project_type == project_type)

    @classmethod
    def default_templates(cls) -> "TemplateLibrary":
        """Return a library pre-loaded with built-in templates."""
        defaults = (
            ProjectTemplate(
                name="python-cli",
                project_type=ProjectType.PYTHON,
                files=(
                    ("pyproject.toml", _PYPROJECT_TOML),
                    ("src/__init__.py", ""),
                    ("tests/__init__.py", ""),
                    ("tests/test_main.py", _PYTHON_TEST),
                ),
                description="Python CLI application with pyproject.toml",
            ),
            ProjectTemplate(
                name="python-lib",
                project_type=ProjectType.PYTHON,
                files=(
                    ("pyproject.toml", _PYPROJECT_TOML),
                    ("src/__init__.py", '"""Library root."""\n'),
                    ("tests/__init__.py", ""),
                ),
                description="Python library with pyproject.toml",
            ),
            ProjectTemplate(
                name="node-app",
                project_type=ProjectType.NODE,
                files=(
                    ("package.json", _PACKAGE_JSON),
                    ("src/index.js", 'console.log("hello");\n'),
                    ("tsconfig.json", _TSCONFIG),
                ),
                description="Node.js application with TypeScript",
            ),
            ProjectTemplate(
                name="rust-cli",
                project_type=ProjectType.RUST,
                files=(
                    ("Cargo.toml", _CARGO_TOML),
                    ("src/main.rs", 'fn main() {\n    println!("hello");\n}\n'),
                ),
                description="Rust CLI application",
            ),
            ProjectTemplate(
                name="go-app",
                project_type=ProjectType.GO,
                files=(
                    ("go.mod", "module example.com/app\n\ngo 1.21\n"),
                    ("main.go", _GO_MAIN),
                ),
                description="Go application",
            ),
        )
        return cls(defaults)


# -- template contents --------------------------------------------------

_PYPROJECT_TOML = """\
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "myproject"
version = "0.1.0"
requires-python = ">=3.11"
"""

_PYTHON_TEST = """\
\"\"\"Placeholder test.\"\"\"


def test_placeholder():
    assert True
"""

_PACKAGE_JSON = """\
{
  "name": "myproject",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "build": "tsc",
    "test": "jest"
  }
}
"""

_TSCONFIG = """\
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "strict": true,
    "outDir": "dist"
  },
  "include": ["src"]
}
"""

_CARGO_TOML = """\
[package]
name = "myproject"
version = "0.1.0"
edition = "2021"
"""

_GO_MAIN = """\
package main

import "fmt"

func main() {
\tfmt.Println("hello")
}
"""
