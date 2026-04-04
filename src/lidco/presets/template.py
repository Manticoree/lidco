"""SessionTemplate and TemplateStore — pre-configured session setups."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict


@dataclass
class SessionTemplate:
    """A pre-configured session template."""

    name: str
    description: str = ""
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    version: int = 1


class TemplateStore:
    """Store for session templates."""

    def __init__(self) -> None:
        self._templates: dict[str, SessionTemplate] = {}

    def register(self, template: SessionTemplate) -> SessionTemplate:
        """Register a template. Overwrites if name exists."""
        self._templates[template.name] = template
        return template

    def get(self, name: str) -> SessionTemplate | None:
        """Get template by name."""
        return self._templates.get(name)

    def remove(self, name: str) -> bool:
        """Remove template by name. Returns True if removed."""
        if name in self._templates:
            del self._templates[name]
            return True
        return False

    def find_by_tag(self, tag: str) -> list[SessionTemplate]:
        """Find templates that contain the given tag."""
        return [t for t in self._templates.values() if tag in t.tags]

    def all_templates(self) -> list[SessionTemplate]:
        """Return all registered templates."""
        return list(self._templates.values())

    def export(self, name: str) -> str:
        """Export a template as JSON string. Raises KeyError if not found."""
        template = self._templates.get(name)
        if template is None:
            raise KeyError(f"Template '{name}' not found")
        return json.dumps(asdict(template), indent=2)

    def import_template(self, json_str: str) -> SessionTemplate:
        """Import a template from JSON string and register it."""
        data = json.loads(json_str)
        template = SessionTemplate(**data)
        self._templates[template.name] = template
        return template

    def summary(self) -> dict:
        """Return a summary of the store."""
        return {
            "total": len(self._templates),
            "names": sorted(self._templates.keys()),
        }
