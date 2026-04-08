"""Pulumi Generator — Generate Pulumi programs in TypeScript/Python, resource grouping, stack management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PulumiResource:
    """A Pulumi resource declaration."""

    name: str
    resource_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    group: str = ""

    def render_python(self) -> str:
        provider, _, rtype = self.resource_type.rpartition(":")
        var_name = self.name.replace("-", "_")
        props = _py_dict(self.properties) if self.properties else "{}"
        return f'{var_name} = {self.resource_type}("{self.name}", {props})'

    def render_typescript(self) -> str:
        var_name = _camel(self.name)
        props = _ts_obj(self.properties) if self.properties else "{}"
        return f'const {var_name} = new {self.resource_type}("{self.name}", {props});'


@dataclass(frozen=True)
class PulumiStack:
    """Stack configuration."""

    name: str
    config: dict[str, str] = field(default_factory=dict)

    def render_yaml(self) -> str:
        lines = [f"config:"]
        for k, v in self.config.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)


@dataclass
class PulumiProgram:
    """Complete Pulumi program."""

    project_name: str
    language: str = "python"  # "python" | "typescript"
    resources: list[PulumiResource] = field(default_factory=list)
    stacks: list[PulumiStack] = field(default_factory=list)

    def render(self) -> dict[str, str]:
        files: dict[str, str] = {}

        # Pulumi.yaml
        files["Pulumi.yaml"] = (
            f"name: {self.project_name}\n"
            f"runtime: {'nodejs' if self.language == 'typescript' else self.language}\n"
            f"description: {self.project_name} infrastructure\n"
        )

        # Stack configs
        for stack in self.stacks:
            files[f"Pulumi.{stack.name}.yaml"] = stack.render_yaml()

        # Main program
        if self.language == "typescript":
            files["index.ts"] = self._render_typescript()
        else:
            files["__main__.py"] = self._render_python()

        return files

    def grouped_resources(self) -> dict[str, list[PulumiResource]]:
        groups: dict[str, list[PulumiResource]] = {}
        for r in self.resources:
            key = r.group or "default"
            groups.setdefault(key, []).append(r)
        return groups

    def _render_python(self) -> str:
        lines = ['"""Pulumi program for ' + self.project_name + '."""', ""]
        imports: set[str] = set()
        for r in self.resources:
            provider = r.resource_type.split(":")[0] if ":" in r.resource_type else "pulumi"
            imports.add(f"import pulumi_{provider}")
        lines.extend(sorted(imports))
        if imports:
            lines.append("")

        groups = self.grouped_resources()
        for group_name, resources in groups.items():
            if group_name != "default":
                lines.append(f"# --- {group_name} ---")
            for r in resources:
                lines.append(r.render_python())
            lines.append("")

        return "\n".join(lines)

    def _render_typescript(self) -> str:
        lines: list[str] = []
        imports: set[str] = set()
        for r in self.resources:
            provider = r.resource_type.split(":")[0] if ":" in r.resource_type else "pulumi"
            imports.add(f'import * as {provider} from "@pulumi/{provider}";')
        lines.extend(sorted(imports))
        if imports:
            lines.append("")

        groups = self.grouped_resources()
        for group_name, resources in groups.items():
            if group_name != "default":
                lines.append(f"// --- {group_name} ---")
            for r in resources:
                lines.append(r.render_typescript())
            lines.append("")

        return "\n".join(lines)


class PulumiGenerator:
    """High-level generator that builds PulumiProgram from specs."""

    def __init__(
        self,
        project_name: str = "my-infra",
        language: str = "python",
    ) -> None:
        self._program = PulumiProgram(
            project_name=project_name, language=language
        )

    @property
    def program(self) -> PulumiProgram:
        return self._program

    def add_resource(
        self,
        name: str,
        resource_type: str,
        group: str = "",
        **properties: Any,
    ) -> PulumiGenerator:
        resource = PulumiResource(
            name=name,
            resource_type=resource_type,
            properties=properties,
            group=group,
        )
        return self._copy(resources=[*self._program.resources, resource])

    def add_stack(
        self,
        name: str,
        **config: str,
    ) -> PulumiGenerator:
        stack = PulumiStack(name=name, config=config)
        return self._copy(stacks=[*self._program.stacks, stack])

    def generate(self) -> dict[str, str]:
        return self._program.render()

    # -- internal -------------------------------------------------------

    def _copy(self, **overrides: Any) -> PulumiGenerator:
        new = PulumiGenerator.__new__(PulumiGenerator)
        new._program = PulumiProgram(
            project_name=self._program.project_name,
            language=self._program.language,
            resources=overrides.get("resources", self._program.resources),
            stacks=overrides.get("stacks", self._program.stacks),
        )
        return new


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _py_dict(d: dict[str, Any]) -> str:
    """Render a dict as a Python dict literal."""
    parts = []
    for k, v in d.items():
        parts.append(f'"{k}": {_py_val(v)}')
    return "{" + ", ".join(parts) + "}"


def _py_val(v: Any) -> str:
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return _py_dict(v)
    if isinstance(v, list):
        return "[" + ", ".join(_py_val(i) for i in v) + "]"
    return f'"{v}"'


def _ts_obj(d: dict[str, Any]) -> str:
    parts = []
    for k, v in d.items():
        parts.append(f"{k}: {_ts_val(v)}")
    return "{ " + ", ".join(parts) + " }"


def _ts_val(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dict):
        return _ts_obj(v)
    if isinstance(v, list):
        return "[" + ", ".join(_ts_val(i) for i in v) + "]"
    return f'"{v}"'


def _camel(name: str) -> str:
    """Convert kebab-case to camelCase."""
    parts = name.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])
