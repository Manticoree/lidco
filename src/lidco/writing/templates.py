"""Writing Templates — RFC, design doc, postmortem, runbook, readme templates.

Fill-in-blank templates with customizable sections.  Pure stdlib.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TemplateSection:
    """One section inside a writing template."""

    title: str
    placeholder: str  # default text / instruction
    required: bool = True


@dataclass
class WritingTemplate:
    """A complete writing template."""

    name: str
    description: str
    sections: list[TemplateSection] = field(default_factory=list)
    variables: list[str] = field(default_factory=list)

    def render(self, values: Mapping[str, str] | None = None) -> str:
        """Render template, substituting ``{{var}}`` placeholders."""
        vals = dict(values) if values else {}
        lines: list[str] = [f"# {self.name}", ""]
        for section in self.sections:
            lines.append(f"## {section.title}")
            text = section.placeholder
            for var in self.variables:
                token = "{{" + var + "}}"
                if token in text:
                    text = text.replace(token, vals.get(var, token))
            lines.append(text)
            lines.append("")
        return "\n".join(lines)

    @property
    def required_sections(self) -> list[TemplateSection]:
        return [s for s in self.sections if s.required]


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

def _rfc_template() -> WritingTemplate:
    return WritingTemplate(
        name="RFC",
        description="Request for Comments — propose a significant change",
        sections=[
            TemplateSection("Summary", "One-paragraph summary of the proposal."),
            TemplateSection("Motivation", "Why is this change needed? What problem does it solve?"),
            TemplateSection("Detailed Design", "Technical design details. Include diagrams if helpful."),
            TemplateSection("Alternatives Considered", "What other approaches were considered and why were they rejected?"),
            TemplateSection("Migration Plan", "How will existing users/systems be migrated?"),
            TemplateSection("Drawbacks", "What are the downsides of this approach?"),
            TemplateSection("Open Questions", "Unresolved questions for discussion.", required=False),
        ],
        variables=["author", "date", "status"],
    )


def _design_doc_template() -> WritingTemplate:
    return WritingTemplate(
        name="Design Document",
        description="Technical design document for a feature or system",
        sections=[
            TemplateSection("Overview", "High-level description of the system/feature."),
            TemplateSection("Goals and Non-Goals", "What this design aims to achieve and explicitly excludes."),
            TemplateSection("Background", "Context and prior art."),
            TemplateSection("Architecture", "System architecture, components, and interactions."),
            TemplateSection("Data Model", "Key data structures and storage.", required=False),
            TemplateSection("API Design", "Public interfaces and contracts.", required=False),
            TemplateSection("Security Considerations", "Authentication, authorization, data protection."),
            TemplateSection("Testing Strategy", "How the system will be tested."),
            TemplateSection("Rollout Plan", "Deployment strategy and feature flags."),
        ],
        variables=["author", "date", "reviewers"],
    )


def _postmortem_template() -> WritingTemplate:
    return WritingTemplate(
        name="Postmortem",
        description="Incident postmortem / retrospective",
        sections=[
            TemplateSection("Incident Summary", "What happened, when, and severity."),
            TemplateSection("Timeline", "Chronological sequence of events (use UTC times)."),
            TemplateSection("Root Cause", "The underlying cause of the incident."),
            TemplateSection("Impact", "Users affected, duration, data loss, revenue impact."),
            TemplateSection("Detection", "How the incident was detected and by whom."),
            TemplateSection("Resolution", "Steps taken to resolve the incident."),
            TemplateSection("Action Items", "Concrete follow-up tasks with owners and deadlines."),
            TemplateSection("Lessons Learned", "What went well and what could be improved.", required=False),
        ],
        variables=["author", "date", "incident_id", "severity"],
    )


def _runbook_template() -> WritingTemplate:
    return WritingTemplate(
        name="Runbook",
        description="Operational runbook for a service or procedure",
        sections=[
            TemplateSection("Service Overview", "What the service does and its dependencies."),
            TemplateSection("Prerequisites", "Required access, tools, and permissions."),
            TemplateSection("Common Operations", "Step-by-step instructions for routine tasks."),
            TemplateSection("Troubleshooting", "Common issues and their resolutions."),
            TemplateSection("Escalation", "When and how to escalate issues."),
            TemplateSection("Monitoring & Alerts", "Key metrics and alert thresholds.", required=False),
            TemplateSection("Recovery Procedures", "Disaster recovery and rollback steps."),
        ],
        variables=["service_name", "team", "last_updated"],
    )


def _readme_template() -> WritingTemplate:
    return WritingTemplate(
        name="README",
        description="Project README for a repository",
        sections=[
            TemplateSection("Project Name", "{{project_name}} — one-line description."),
            TemplateSection("Installation", "How to install and set up the project."),
            TemplateSection("Usage", "Basic usage examples and commands."),
            TemplateSection("Configuration", "Environment variables and config files.", required=False),
            TemplateSection("Contributing", "How to contribute to the project.", required=False),
            TemplateSection("License", "License information."),
        ],
        variables=["project_name", "author", "license"],
    )


# ---------------------------------------------------------------------------
# Template Library
# ---------------------------------------------------------------------------

class TemplateLibrary:
    """Manage writing templates with built-in defaults and custom additions."""

    def __init__(self) -> None:
        self._templates: dict[str, WritingTemplate] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        for factory in (_rfc_template, _design_doc_template, _postmortem_template,
                        _runbook_template, _readme_template):
            tpl = factory()
            self._templates[tpl.name.lower()] = tpl

    # -- public API ----------------------------------------------------------

    def list_templates(self) -> list[WritingTemplate]:
        """Return all available templates."""
        return list(self._templates.values())

    def get(self, name: str) -> WritingTemplate | None:
        """Get a template by name (case-insensitive)."""
        return self._templates.get(name.lower())

    def add(self, template: WritingTemplate) -> None:
        """Add or replace a custom template."""
        self._templates[template.name.lower()] = template

    def remove(self, name: str) -> bool:
        """Remove a template. Returns True if found and removed."""
        key = name.lower()
        if key in self._templates:
            del self._templates[key]
            return True
        return False

    def render(self, name: str, values: Mapping[str, str] | None = None) -> str | None:
        """Render a template by name. Returns None if not found."""
        tpl = self.get(name)
        if tpl is None:
            return None
        return tpl.render(values)

    @property
    def count(self) -> int:
        return len(self._templates)
