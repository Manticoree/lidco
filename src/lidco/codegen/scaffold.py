"""ScaffoldGenerator — project scaffolding from presets."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScaffoldSpec:
    """Specification for a scaffolded project."""

    name: str
    type: str
    files: list[dict[str, str]] = field(default_factory=list)


# -- Preset factories ----------------------------------------------------

_PRESETS: dict[str, list[dict[str, str]]] = {
    "api": [
        {"path": "app/__init__.py", "content": ""},
        {"path": "app/main.py", "content": 'from __future__ import annotations\n\n\ndef create_app(name: str) -> dict:\n    return {{"name": name}}\n'},
        {"path": "app/routes.py", "content": "from __future__ import annotations\n\nROUTES: list[str] = []\n"},
        {"path": "tests/__init__.py", "content": ""},
        {"path": "tests/test_main.py", "content": "from __future__ import annotations\n\n\ndef test_placeholder() -> None:\n    assert True\n"},
        {"path": "requirements.txt", "content": ""},
        {"path": "README.md", "content": "# {name}\n"},
    ],
    "cli": [
        {"path": "{name}/__init__.py", "content": ""},
        {"path": "{name}/cli.py", "content": "from __future__ import annotations\n\nimport sys\n\n\ndef main() -> None:\n    print('Hello from {name}')\n\n\nif __name__ == '__main__':\n    main()\n"},
        {"path": "tests/__init__.py", "content": ""},
        {"path": "tests/test_cli.py", "content": "from __future__ import annotations\n\n\ndef test_placeholder() -> None:\n    assert True\n"},
        {"path": "pyproject.toml", "content": '[project]\nname = "{name}"\nversion = "0.1.0"\n'},
    ],
    "library": [
        {"path": "src/{name}/__init__.py", "content": '"""Top-level package for {name}."""\n\n__version__ = "0.1.0"\n'},
        {"path": "src/{name}/core.py", "content": "from __future__ import annotations\n"},
        {"path": "tests/__init__.py", "content": ""},
        {"path": "tests/test_core.py", "content": "from __future__ import annotations\n\n\ndef test_placeholder() -> None:\n    assert True\n"},
        {"path": "pyproject.toml", "content": '[project]\nname = "{name}"\nversion = "0.1.0"\n'},
    ],
}


class ScaffoldGenerator:
    """Generate project scaffolding from a :class:`ScaffoldSpec`."""

    def generate(self, spec: ScaffoldSpec) -> dict[str, str]:
        """Return a mapping of *filepath* -> *content* for the scaffold."""
        result: dict[str, str] = {}
        for entry in spec.files:
            path = entry.get("path", "")
            content = entry.get("content", "")
            path = path.replace("{name}", spec.name)
            content = content.replace("{name}", spec.name)
            result[path] = content
        return result

    def from_type(self, project_type: str, name: str) -> ScaffoldSpec:
        """Create a :class:`ScaffoldSpec` from a preset *project_type*."""
        preset = _PRESETS.get(project_type)
        if preset is None:
            raise ValueError(
                f"Unknown project type: {project_type!r}. "
                f"Available: {', '.join(sorted(_PRESETS))}"
            )
        return ScaffoldSpec(name=name, type=project_type, files=list(preset))

    def preview(self, spec: ScaffoldSpec) -> str:
        """Return a file-tree preview string for *spec*."""
        generated = self.generate(spec)
        if not generated:
            return "(empty scaffold)"
        lines = [f"{spec.name}/"]
        sorted_paths = sorted(generated)
        for path in sorted_paths:
            depth = path.count("/")
            indent = "  " * depth
            basename = path.rsplit("/", 1)[-1] if "/" in path else path
            lines.append(f"{indent}{basename}")
        return "\n".join(lines)
