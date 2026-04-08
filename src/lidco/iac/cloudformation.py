"""CloudFormation Generator — Generate CF templates, nested stacks, parameter store, output exports, drift detection."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CFParameter:
    """A CloudFormation parameter."""

    name: str
    type: str = "String"
    description: str = ""
    default: str = ""
    allowed_values: list[str] = field(default_factory=list)

    def render(self) -> dict[str, Any]:
        d: dict[str, Any] = {"Type": self.type}
        if self.description:
            d["Description"] = self.description
        if self.default:
            d["Default"] = self.default
        if self.allowed_values:
            d["AllowedValues"] = list(self.allowed_values)
        return d


@dataclass(frozen=True)
class CFResource:
    """A CloudFormation resource."""

    logical_id: str
    resource_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)

    def render(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "Type": self.resource_type,
        }
        if self.properties:
            d["Properties"] = dict(self.properties)
        if self.depends_on:
            d["DependsOn"] = list(self.depends_on)
        return d


@dataclass(frozen=True)
class CFOutput:
    """A CloudFormation output."""

    name: str
    value: Any
    description: str = ""
    export_name: str = ""

    def render(self) -> dict[str, Any]:
        d: dict[str, Any] = {"Value": self.value}
        if self.description:
            d["Description"] = self.description
        if self.export_name:
            d["Export"] = {"Name": self.export_name}
        return d


@dataclass(frozen=True)
class NestedStack:
    """A nested CloudFormation stack resource."""

    logical_id: str
    template_url: str
    parameters: dict[str, str] = field(default_factory=dict)

    def as_resource(self) -> CFResource:
        props: dict[str, Any] = {"TemplateURL": self.template_url}
        if self.parameters:
            props["Parameters"] = dict(self.parameters)
        return CFResource(
            logical_id=self.logical_id,
            resource_type="AWS::CloudFormation::Stack",
            properties=props,
        )


@dataclass
class CFTemplate:
    """Complete CloudFormation template."""

    description: str = ""
    parameters: list[CFParameter] = field(default_factory=list)
    resources: list[CFResource] = field(default_factory=list)
    outputs: list[CFOutput] = field(default_factory=list)
    nested_stacks: list[NestedStack] = field(default_factory=list)

    def render(self) -> dict[str, Any]:
        tpl: dict[str, Any] = {
            "AWSTemplateFormatVersion": "2010-09-09",
        }
        if self.description:
            tpl["Description"] = self.description

        if self.parameters:
            tpl["Parameters"] = {p.name: p.render() for p in self.parameters}

        resources: dict[str, Any] = {}
        for r in self.resources:
            resources[r.logical_id] = r.render()
        for ns in self.nested_stacks:
            res = ns.as_resource()
            resources[res.logical_id] = res.render()
        if resources:
            tpl["Resources"] = resources

        if self.outputs:
            tpl["Outputs"] = {o.name: o.render() for o in self.outputs}

        return tpl

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.render(), indent=indent)


@dataclass(frozen=True)
class DriftResult:
    """Result of drift detection between two templates."""

    has_drift: bool
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)


class CloudFormationGenerator:
    """High-level generator that builds CFTemplate from specs."""

    def __init__(self, description: str = "") -> None:
        self._template = CFTemplate(description=description)

    @property
    def template(self) -> CFTemplate:
        return self._template

    def add_parameter(
        self,
        name: str,
        type: str = "String",
        description: str = "",
        default: str = "",
        allowed_values: list[str] | None = None,
    ) -> CloudFormationGenerator:
        param = CFParameter(
            name=name,
            type=type,
            description=description,
            default=default,
            allowed_values=allowed_values or [],
        )
        return self._copy(parameters=[*self._template.parameters, param])

    def add_resource(
        self,
        logical_id: str,
        resource_type: str,
        properties: dict[str, Any] | None = None,
        depends_on: list[str] | None = None,
    ) -> CloudFormationGenerator:
        resource = CFResource(
            logical_id=logical_id,
            resource_type=resource_type,
            properties=properties or {},
            depends_on=depends_on or [],
        )
        return self._copy(resources=[*self._template.resources, resource])

    def add_output(
        self,
        name: str,
        value: Any,
        description: str = "",
        export_name: str = "",
    ) -> CloudFormationGenerator:
        out = CFOutput(
            name=name, value=value, description=description, export_name=export_name
        )
        return self._copy(outputs=[*self._template.outputs, out])

    def add_nested_stack(
        self,
        logical_id: str,
        template_url: str,
        parameters: dict[str, str] | None = None,
    ) -> CloudFormationGenerator:
        ns = NestedStack(
            logical_id=logical_id,
            template_url=template_url,
            parameters=parameters or {},
        )
        return self._copy(nested_stacks=[*self._template.nested_stacks, ns])

    def generate(self) -> dict[str, str]:
        """Return dict of filename -> content."""
        return {"template.json": self._template.to_json()}

    # -- drift detection ------------------------------------------------

    @staticmethod
    def detect_drift(
        expected: CFTemplate,
        actual: CFTemplate,
    ) -> DriftResult:
        expected_ids = {r.logical_id for r in expected.resources}
        actual_ids = {r.logical_id for r in actual.resources}

        added = sorted(actual_ids - expected_ids)
        removed = sorted(expected_ids - actual_ids)

        expected_map = {r.logical_id: r for r in expected.resources}
        actual_map = {r.logical_id: r for r in actual.resources}

        modified: list[str] = []
        for rid in sorted(expected_ids & actual_ids):
            if expected_map[rid] != actual_map[rid]:
                modified.append(rid)

        has_drift = bool(added or removed or modified)
        return DriftResult(
            has_drift=has_drift,
            added=added,
            removed=removed,
            modified=modified,
        )

    # -- internal -------------------------------------------------------

    def _copy(self, **overrides: Any) -> CloudFormationGenerator:
        new = CloudFormationGenerator.__new__(CloudFormationGenerator)
        new._template = CFTemplate(
            description=overrides.get("description", self._template.description),
            parameters=overrides.get("parameters", self._template.parameters),
            resources=overrides.get("resources", self._template.resources),
            outputs=overrides.get("outputs", self._template.outputs),
            nested_stacks=overrides.get("nested_stacks", self._template.nested_stacks),
        )
        return new
