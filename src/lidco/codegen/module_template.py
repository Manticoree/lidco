"""Module Template — generate Python module source files.

Stdlib only — no external deps.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModuleConfig:
    """Configuration for module code generation."""
    name: str
    description: str = ""
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    docstring: str = ""


class ModuleTemplate:
    """Generate Python module source from ModuleConfig."""

    def render(self, config: ModuleConfig) -> str:
        """Generate full module with header, imports, and __all__."""
        parts: list[str] = []

        header = self.render_header(config)
        if header:
            parts.append(header)

        if config.imports:
            import_lines = "\n".join(config.imports)
            parts.append(import_lines)

        if config.exports:
            all_line = self.render_all(config.exports)
            parts.append(all_line)

        if not parts:
            parts.append("# Empty module")

        return "\n\n".join(parts) + "\n"

    def render_header(self, config: ModuleConfig) -> str:
        """Generate a module docstring header."""
        doc = config.docstring or config.description
        if not doc:
            return f'"""{config.name}"""'
        return f'"""{doc}"""'

    def render_all(self, exports: list[str]) -> str:
        """Generate __all__ = [...] declaration."""
        if not exports:
            return "__all__: list[str] = []"
        quoted = ", ".join(f'"{name}"' for name in exports)
        return f"__all__ = [{quoted}]"
