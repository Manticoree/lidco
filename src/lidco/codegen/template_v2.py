"""TemplateEngineV2 — code generation template engine with control flow."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Template:
    """A named code generation template."""

    name: str
    language: str
    body: str
    variables: list[str] = field(default_factory=list)


class TemplateEngineV2:
    """Register, render, and list code-generation templates.

    Supports ``{{var}}``, ``{% if var %}...{% endif %}``,
    and ``{% for item in list %}...{% endfor %}`` directives.
    """

    _IF_RE = re.compile(
        r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}",
        re.DOTALL,
    )
    _FOR_RE = re.compile(
        r"\{%\s*for\s+(\w+)\s+in\s+(\w+)\s*%\}(.*?)\{%\s*endfor\s*%\}",
        re.DOTALL,
    )
    _VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

    def __init__(self) -> None:
        self._templates: dict[str, Template] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, template: Template) -> None:
        """Register *template* (overwrites if name exists)."""
        self._templates = {**self._templates, template.name: template}

    def render(self, name: str, variables: dict[str, object] | None = None) -> str:
        """Render the template identified by *name* with *variables*."""
        tpl = self._templates.get(name)
        if tpl is None:
            raise KeyError(f"Template not found: {name}")
        variables = variables or {}
        text = tpl.body
        text = self._process_ifs(text, variables)
        text = self._process_fors(text, variables)
        text = self._process_vars(text, variables)
        return text

    def list_templates(self) -> list[Template]:
        """Return all registered templates ordered by name."""
        return sorted(self._templates.values(), key=lambda t: t.name)

    def get(self, name: str) -> Template | None:
        """Return the template named *name*, or ``None``."""
        return self._templates.get(name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_ifs(self, text: str, variables: dict[str, object]) -> str:
        def _replace(m: re.Match[str]) -> str:
            var_name = m.group(1)
            body = m.group(2)
            if variables.get(var_name):
                return body
            return ""

        return self._IF_RE.sub(_replace, text)

    def _process_fors(self, text: str, variables: dict[str, object]) -> str:
        def _replace(m: re.Match[str]) -> str:
            item_name = m.group(1)
            list_name = m.group(2)
            body = m.group(3)
            items = variables.get(list_name, [])
            if not isinstance(items, (list, tuple)):
                return ""
            parts: list[str] = []
            for item in items:
                rendered = self._VAR_RE.sub(
                    lambda vm: (
                        str(item) if vm.group(1) == item_name else str(variables.get(vm.group(1), vm.group(0)))
                    ),
                    body,
                )
                parts.append(rendered)
            return "".join(parts)

        return self._FOR_RE.sub(_replace, text)

    def _process_vars(self, text: str, variables: dict[str, object]) -> str:
        def _replace(m: re.Match[str]) -> str:
            return str(variables.get(m.group(1), m.group(0)))

        return self._VAR_RE.sub(_replace, text)
