"""Terraform Generator — Generate Terraform configs, modules, variables, outputs, state management, provider configs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TerraformVariable:
    """A Terraform input variable."""

    name: str
    type: str = "string"
    description: str = ""
    default: Any = None
    sensitive: bool = False

    def render(self) -> str:
        lines = [f'variable "{self.name}" {{']
        lines.append(f"  type        = {self.type}")
        if self.description:
            lines.append(f'  description = "{self.description}"')
        if self.default is not None:
            lines.append(f"  default     = {_tf_value(self.default)}")
        if self.sensitive:
            lines.append("  sensitive   = true")
        lines.append("}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TerraformOutput:
    """A Terraform output."""

    name: str
    value: str
    description: str = ""
    sensitive: bool = False

    def render(self) -> str:
        lines = [f'output "{self.name}" {{']
        lines.append(f"  value       = {self.value}")
        if self.description:
            lines.append(f'  description = "{self.description}"')
        if self.sensitive:
            lines.append("  sensitive   = true")
        lines.append("}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TerraformResource:
    """A Terraform resource block."""

    resource_type: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        lines = [f'resource "{self.resource_type}" "{self.name}" {{']
        for k, v in self.attributes.items():
            lines.append(f"  {k} = {_tf_value(v)}")
        lines.append("}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TerraformProvider:
    """A Terraform provider block."""

    name: str
    region: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        lines = [f'provider "{self.name}" {{']
        if self.region:
            lines.append(f'  region = "{self.region}"')
        for k, v in self.attributes.items():
            lines.append(f"  {k} = {_tf_value(v)}")
        lines.append("}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TerraformModule:
    """A Terraform module call."""

    name: str
    source: str
    variables: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        lines = [f'module "{self.name}" {{']
        lines.append(f'  source = "{self.source}"')
        for k, v in self.variables.items():
            lines.append(f"  {k} = {_tf_value(v)}")
        lines.append("}")
        return "\n".join(lines)


@dataclass(frozen=True)
class StateConfig:
    """Terraform backend state configuration."""

    backend: str = "local"
    config: dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        lines = ["terraform {", f'  backend "{self.backend}" {{']
        for k, v in self.config.items():
            lines.append(f'    {k} = "{v}"')
        lines.append("  }")
        lines.append("}")
        return "\n".join(lines)


@dataclass
class TerraformConfig:
    """Complete Terraform configuration."""

    providers: list[TerraformProvider] = field(default_factory=list)
    resources: list[TerraformResource] = field(default_factory=list)
    variables: list[TerraformVariable] = field(default_factory=list)
    outputs: list[TerraformOutput] = field(default_factory=list)
    modules: list[TerraformModule] = field(default_factory=list)
    state: StateConfig | None = None

    def render(self) -> dict[str, str]:
        """Render to a dict of filename -> content."""
        files: dict[str, str] = {}

        # main.tf
        main_parts: list[str] = []
        if self.state:
            main_parts.append(self.state.render())
        for p in self.providers:
            main_parts.append(p.render())
        for r in self.resources:
            main_parts.append(r.render())
        for m in self.modules:
            main_parts.append(m.render())
        if main_parts:
            files["main.tf"] = "\n\n".join(main_parts) + "\n"

        # variables.tf
        if self.variables:
            files["variables.tf"] = (
                "\n\n".join(v.render() for v in self.variables) + "\n"
            )

        # outputs.tf
        if self.outputs:
            files["outputs.tf"] = (
                "\n\n".join(o.render() for o in self.outputs) + "\n"
            )

        return files


class TerraformGenerator:
    """High-level generator that builds TerraformConfig from specs."""

    def __init__(self) -> None:
        self._config = TerraformConfig()

    @property
    def config(self) -> TerraformConfig:
        return self._config

    def add_provider(
        self,
        name: str,
        region: str = "",
        **attrs: Any,
    ) -> TerraformGenerator:
        provider = TerraformProvider(name=name, region=region, attributes=attrs)
        return TerraformGenerator._with(
            self, providers=[*self._config.providers, provider]
        )

    def add_resource(
        self,
        resource_type: str,
        name: str,
        **attrs: Any,
    ) -> TerraformGenerator:
        resource = TerraformResource(
            resource_type=resource_type, name=name, attributes=attrs
        )
        return TerraformGenerator._with(
            self, resources=[*self._config.resources, resource]
        )

    def add_variable(
        self,
        name: str,
        type: str = "string",
        description: str = "",
        default: Any = None,
        sensitive: bool = False,
    ) -> TerraformGenerator:
        var = TerraformVariable(
            name=name,
            type=type,
            description=description,
            default=default,
            sensitive=sensitive,
        )
        return TerraformGenerator._with(
            self, variables=[*self._config.variables, var]
        )

    def add_output(
        self,
        name: str,
        value: str,
        description: str = "",
        sensitive: bool = False,
    ) -> TerraformGenerator:
        out = TerraformOutput(
            name=name, value=value, description=description, sensitive=sensitive
        )
        return TerraformGenerator._with(
            self, outputs=[*self._config.outputs, out]
        )

    def add_module(
        self,
        name: str,
        source: str,
        **variables: Any,
    ) -> TerraformGenerator:
        mod = TerraformModule(name=name, source=source, variables=variables)
        return TerraformGenerator._with(
            self, modules=[*self._config.modules, mod]
        )

    def set_state(
        self,
        backend: str = "s3",
        **config: str,
    ) -> TerraformGenerator:
        state = StateConfig(backend=backend, config=config)
        return TerraformGenerator._with(self, state=state)

    def generate(self) -> dict[str, str]:
        """Generate all Terraform files."""
        return self._config.render()

    # -- internal immutable builder helper --------------------------------

    @staticmethod
    def _with(gen: TerraformGenerator, **overrides: Any) -> TerraformGenerator:
        new = TerraformGenerator()
        new._config = TerraformConfig(
            providers=overrides.get("providers", gen._config.providers),
            resources=overrides.get("resources", gen._config.resources),
            variables=overrides.get("variables", gen._config.variables),
            outputs=overrides.get("outputs", gen._config.outputs),
            modules=overrides.get("modules", gen._config.modules),
            state=overrides.get("state", gen._config.state),
        )
        return new


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _tf_value(val: Any) -> str:
    """Format a Python value as a Terraform literal."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, list):
        inner = ", ".join(_tf_value(v) for v in val)
        return f"[{inner}]"
    if isinstance(val, dict):
        inner = ", ".join(f"{k} = {_tf_value(v)}" for k, v in val.items())
        return "{ " + inner + " }"
    return f'"{val}"'
