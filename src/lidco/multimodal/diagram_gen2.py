"""Diagram generation module v2 — Mermaid diagram generation from code structures.

DiagramGenerator2 produces Mermaid-syntax diagrams for class hierarchies,
sequence diagrams, and architecture component diagrams.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ClassInfo:
    """Describes a class for diagram generation."""

    name: str
    methods: list[str] = field(default_factory=list)
    attributes: list[str] = field(default_factory=list)
    parent: str | None = None


@dataclass(frozen=True)
class CallInfo:
    """Describes a call for sequence diagram generation."""

    caller: str
    callee: str
    method: str
    return_type: str = ""


@dataclass(frozen=True)
class ComponentInfo:
    """Describes a component for architecture diagrams."""

    name: str
    kind: str = "service"
    depends_on: list[str] = field(default_factory=list)
    description: str = ""


class DiagramGenerator2:
    """Generate Mermaid-syntax diagrams from code structures."""

    def class_diagram(self, classes: list[ClassInfo]) -> str:
        """Generate a Mermaid class diagram from a list of ClassInfo."""
        if not classes:
            return "classDiagram"
        lines: list[str] = ["classDiagram"]
        for cls in classes:
            lines.append(f"    class {cls.name} {{")
            for attr in cls.attributes:
                lines.append(f"        +{attr}")
            for method in cls.methods:
                lines.append(f"        +{method}()")
            lines.append("    }")
            if cls.parent:
                lines.append(f"    {cls.parent} <|-- {cls.name}")
        return "\n".join(lines)

    def sequence_diagram(self, calls: list[CallInfo]) -> str:
        """Generate a Mermaid sequence diagram from a list of calls."""
        if not calls:
            return "sequenceDiagram"
        lines: list[str] = ["sequenceDiagram"]
        for call in calls:
            arrow = "->>"
            lines.append(f"    {call.caller}{arrow}{call.callee}: {call.method}")
            if call.return_type:
                lines.append(f"    {call.callee}-->>{ call.caller}: {call.return_type}")
        return "\n".join(lines)

    def architecture_diagram(self, components: list[ComponentInfo]) -> str:
        """Generate a Mermaid flowchart representing system architecture."""
        if not components:
            return "flowchart TD"
        lines: list[str] = ["flowchart TD"]
        for comp in components:
            shape = self._shape_for_kind(comp.kind)
            label = comp.description if comp.description else comp.name
            lines.append(f"    {comp.name}{shape[0]}{label}{shape[1]}")
        for comp in components:
            for dep in comp.depends_on:
                lines.append(f"    {comp.name} --> {dep}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _shape_for_kind(kind: str) -> tuple[str, str]:
        """Return Mermaid shape delimiters based on component kind."""
        shapes: dict[str, tuple[str, str]] = {
            "service": ("[", "]"),
            "database": ("[(", ")]"),
            "queue": ("[[", "]]"),
            "gateway": ("{", "}"),
            "external": ("((", "))"),
        }
        return shapes.get(kind, ("[", "]"))
