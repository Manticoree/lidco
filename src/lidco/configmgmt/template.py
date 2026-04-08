"""Config Template Engine — generate config files from templates.

Environment-specific values, secrets injection, validation.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TemplateVariable:
    """A variable placeholder within a config template."""

    name: str
    default: str | None = None
    required: bool = True
    secret: bool = False
    description: str = ""


@dataclass(frozen=True)
class RenderResult:
    """Result of rendering a config template."""

    content: str
    variables_used: list[str] = field(default_factory=list)
    secrets_injected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TemplateValidationError(Exception):
    """Raised when template validation fails."""


class ConfigTemplateEngine:
    """Generate config files from templates with environment-specific values.

    Supports ``{{VAR}}`` and ``{{VAR|default}}`` placeholders.
    Secrets are resolved from a secrets provider callback or env vars.
    """

    _PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\|\s*([^}]*))?\s*\}\}")

    def __init__(self) -> None:
        self._templates: dict[str, str] = {}
        self._environments: dict[str, dict[str, str]] = {}
        self._secrets_provider: Any | None = None

    # -- Template management ------------------------------------------------

    def register_template(self, name: str, content: str) -> None:
        """Register a named template."""
        if not name:
            raise ValueError("Template name must not be empty")
        self._templates[name] = content

    def list_templates(self) -> list[str]:
        """Return registered template names."""
        return sorted(self._templates)

    def get_template(self, name: str) -> str:
        """Return raw template content."""
        if name not in self._templates:
            raise KeyError(f"Template not found: {name}")
        return self._templates[name]

    def remove_template(self, name: str) -> None:
        """Remove a registered template."""
        self._templates.pop(name, None)

    # -- Environment management --------------------------------------------

    def register_environment(self, name: str, values: dict[str, str]) -> None:
        """Register an environment with its variable values."""
        self._environments[name] = dict(values)

    def list_environments(self) -> list[str]:
        """Return registered environment names."""
        return sorted(self._environments)

    def get_environment(self, name: str) -> dict[str, str]:
        """Return a copy of environment values."""
        if name not in self._environments:
            raise KeyError(f"Environment not found: {name}")
        return dict(self._environments[name])

    # -- Secrets ------------------------------------------------------------

    def set_secrets_provider(self, provider: Any) -> None:
        """Set a callable ``(key: str) -> str | None`` that resolves secrets."""
        self._secrets_provider = provider

    # -- Parsing / introspection -------------------------------------------

    def extract_variables(self, template_name: str) -> list[TemplateVariable]:
        """Extract all variable placeholders from a template."""
        content = self.get_template(template_name)
        seen: dict[str, TemplateVariable] = {}
        for match in self._PLACEHOLDER_RE.finditer(content):
            var_name = match.group(1)
            default = match.group(2)
            if default is not None:
                default = default.strip()
            if var_name not in seen:
                seen[var_name] = TemplateVariable(
                    name=var_name,
                    default=default,
                    required=default is None,
                )
        return list(seen.values())

    # -- Rendering ---------------------------------------------------------

    def render(
        self,
        template_name: str,
        environment: str | None = None,
        overrides: dict[str, str] | None = None,
        *,
        strict: bool = True,
    ) -> RenderResult:
        """Render a template with environment values + overrides.

        Parameters
        ----------
        template_name:
            Name of a registered template.
        environment:
            Optional registered environment name.
        overrides:
            Extra key/value pairs that take precedence over the environment.
        strict:
            If ``True`` (default), raise on missing required variables.
        """
        content = self.get_template(template_name)
        env_vals: dict[str, str] = {}
        if environment is not None:
            env_vals = dict(self._environments.get(environment, {}))
        if overrides:
            env_vals.update(overrides)

        variables_used: list[str] = []
        secrets_injected: list[str] = []
        warnings: list[str] = []
        missing: list[str] = []

        def _replacer(m: re.Match[str]) -> str:
            var = m.group(1)
            default = m.group(2)
            if default is not None:
                default = default.strip()

            # Priority: overrides/env > secrets provider > env var > default
            value: str | None = env_vals.get(var)
            is_secret = False

            if value is None and self._secrets_provider is not None:
                resolved = self._secrets_provider(var)
                if resolved is not None:
                    value = resolved
                    is_secret = True

            if value is None:
                env_value = os.environ.get(var)
                if env_value is not None:
                    value = env_value

            if value is None and default is not None:
                value = default

            if value is None:
                missing.append(var)
                return m.group(0)  # leave placeholder

            variables_used.append(var)
            if is_secret:
                secrets_injected.append(var)
            return value

        rendered = self._PLACEHOLDER_RE.sub(_replacer, content)

        if missing and strict:
            raise TemplateValidationError(
                f"Missing required variables: {', '.join(missing)}"
            )
        if missing:
            for v in missing:
                warnings.append(f"Unresolved variable: {v}")

        return RenderResult(
            content=rendered,
            variables_used=variables_used,
            secrets_injected=secrets_injected,
            warnings=warnings,
        )

    # -- Validation --------------------------------------------------------

    def validate_template(self, template_name: str, environment: str | None = None) -> list[str]:
        """Validate a template against an environment. Returns list of issues."""
        issues: list[str] = []
        variables = self.extract_variables(template_name)
        env_vals = self._environments.get(environment, {}) if environment else {}

        for var in variables:
            if var.required and var.name not in env_vals:
                # Check env var fallback
                if os.environ.get(var.name) is None:
                    issues.append(f"Missing required variable: {var.name}")

        return issues

    # -- JSON config generation --------------------------------------------

    def render_json(
        self,
        template_name: str,
        environment: str | None = None,
        overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Render a template and parse as JSON."""
        result = self.render(template_name, environment, overrides)
        try:
            return json.loads(result.content)
        except json.JSONDecodeError as exc:
            raise TemplateValidationError(f"Rendered template is not valid JSON: {exc}") from exc
