"""Q131: Lightweight prompt template engine with {{var}}, {% if %}, {% for %} support."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RenderContext:
    variables: dict
    strict: bool = False  # True: raise on undefined var; False: leave as ""


class PromptTemplateEngine:
    """Render prompt templates with variable substitution, conditionals, and loops."""

    # --- public API ----------------------------------------------------------

    def render(self, template: str, context: RenderContext) -> str:
        """Render *template* using *context*."""
        text = self._process_for_blocks(template, context.variables)
        text = self._process_if_blocks(text, context.variables)
        text = self._substitute_vars(text, context.variables, context.strict)
        return text

    def render_dict(self, template: str, variables: dict) -> str:
        """Convenience wrapper: render with a plain dict (non-strict)."""
        return self.render(template, RenderContext(variables=variables))

    def extract_variables(self, template: str) -> list[str]:
        """Return all {{var}} names found in *template* (unique, ordered)."""
        seen: list[str] = []
        seen_set: set[str] = set()
        for name in re.findall(r"\{\{(\w+)\}\}", template):
            if name not in seen_set:
                seen.append(name)
                seen_set.add(name)
        return seen

    def validate(self, template: str, variables: dict) -> list[str]:
        """Return list of variable names referenced in template but not in *variables*."""
        required = self.extract_variables(template)
        return [v for v in required if v not in variables]

    # --- internals -----------------------------------------------------------

    def _substitute_vars(self, text: str, variables: dict, strict: bool) -> str:
        def replacer(m: re.Match) -> str:
            name = m.group(1)
            if name in variables:
                return str(variables[name])
            if strict:
                raise KeyError(f"Undefined template variable: {name!r}")
            return ""

        return re.sub(r"\{\{(\w+)\}\}", replacer, text)

    def _process_if_blocks(self, text: str, variables: dict) -> str:
        """Handle {% if var %} ... {% endif %} (no else support)."""
        pattern = re.compile(
            r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}", re.DOTALL
        )

        def replacer(m: re.Match) -> str:
            var_name = m.group(1)
            body = m.group(2)
            val = variables.get(var_name)
            return body if val else ""

        return pattern.sub(replacer, text)

    def _process_for_blocks(self, text: str, variables: dict) -> str:
        """Handle {% for item in list %} ... {% endfor %}."""
        pattern = re.compile(
            r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}", re.DOTALL
        )

        def replacer(m: re.Match) -> str:
            item_name = m.group(1)
            list_name = m.group(2)
            body = m.group(3)
            items = variables.get(list_name, [])
            parts: list[str] = []
            for item in items:
                local_vars = dict(variables)
                local_vars[item_name] = item
                parts.append(self._substitute_vars(body, local_vars, False))
            return "".join(parts)

        return pattern.sub(replacer, text)
