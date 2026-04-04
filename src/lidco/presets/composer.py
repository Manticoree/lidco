"""PresetComposer — compose, extend, merge, and substitute presets."""
from __future__ import annotations

import copy
import re

from lidco.presets.library import PresetLibrary
from lidco.presets.template import SessionTemplate


class PresetComposer:
    """Compose presets via inheritance, merging, and variable substitution."""

    def __init__(self, library: PresetLibrary) -> None:
        self._library = library

    def extend(self, base_name: str, overrides: dict, new_name: str) -> SessionTemplate:
        """Create a new template by extending a base preset with overrides."""
        base_preset = self._library.get(base_name)
        if base_preset is None:
            raise KeyError(f"Preset '{base_name}' not found")

        base = base_preset.template
        return SessionTemplate(
            name=new_name,
            description=overrides.get("description", base.description),
            system_prompt=overrides.get("system_prompt", base.system_prompt),
            tools=overrides.get("tools", list(base.tools)),
            config={**base.config, **overrides.get("config", {})},
            tags=overrides.get("tags", list(base.tags)),
            version=overrides.get("version", base.version),
        )

    def merge(self, preset_a: str, preset_b: str, new_name: str) -> SessionTemplate:
        """Merge two presets. preset_b overrides preset_a where both have values."""
        pa = self._library.get(preset_a)
        pb = self._library.get(preset_b)
        if pa is None:
            raise KeyError(f"Preset '{preset_a}' not found")
        if pb is None:
            raise KeyError(f"Preset '{preset_b}' not found")

        a = pa.template
        b = pb.template

        merged_tools = list(dict.fromkeys(a.tools + b.tools))
        merged_tags = list(dict.fromkeys(a.tags + b.tags))

        return SessionTemplate(
            name=new_name,
            description=b.description or a.description,
            system_prompt=b.system_prompt or a.system_prompt,
            tools=merged_tools,
            config={**a.config, **b.config},
            tags=merged_tags,
            version=max(a.version, b.version),
        )

    def substitute(
        self, template: SessionTemplate, variables: dict[str, str]
    ) -> SessionTemplate:
        """Replace {{var}} placeholders in system_prompt with variable values."""
        prompt = template.system_prompt
        for key, value in variables.items():
            prompt = prompt.replace("{{" + key + "}}", value)
        return SessionTemplate(
            name=template.name,
            description=template.description,
            system_prompt=prompt,
            tools=list(template.tools),
            config=copy.deepcopy(template.config),
            tags=list(template.tags),
            version=template.version,
        )

    def preview(self, name: str) -> str:
        """Return a text preview of a preset."""
        preset = self._library.get(name)
        if preset is None:
            raise KeyError(f"Preset '{name}' not found")
        t = preset.template
        lines = [
            f"Preset: {preset.name} (v{preset.version})",
            f"Category: {preset.category}",
            f"Author: {preset.author}",
            f"Description: {t.description}",
            f"System Prompt: {t.system_prompt}",
            f"Tools: {', '.join(t.tools) if t.tools else 'none'}",
            f"Tags: {', '.join(t.tags) if t.tags else 'none'}",
        ]
        return "\n".join(lines)

    def summary(self) -> dict:
        """Return a summary."""
        return {
            "library_total": len(self._library.all_presets()),
        }
