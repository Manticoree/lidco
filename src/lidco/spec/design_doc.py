"""DesignDocGenerator — converts SpecDocument → design.md.

Produces a technical design with components, data models, API contracts, and
implementation notes aligned with the existing codebase architecture.
"""
from __future__ import annotations

import logging
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lidco.spec.writer import SpecDocument

logger = logging.getLogger(__name__)

_SPEC_DIR = ".lidco/spec"
_DESIGN_FILE = "design.md"

_SYSTEM_PROMPT = textwrap.dedent("""\
    You are a principal software architect.  Given a requirements document, produce a
    concise technical design document.

    Respond in JSON with exactly this schema:
    {
      "components": [
        {"name": "...", "responsibility": "...", "file_path": "src/..."}
      ],
      "data_models": ["<ClassName>: field1: type, field2: type, ..."],
      "api_contracts": ["function_name(param: type) -> return_type — description"],
      "implementation_notes": "<paragraph with architecture guidance>"
    }

    Rules:
    - components should map to real Python module paths
    - data_models use Python dataclass-style notation
    - api_contracts list public method signatures only
    - implementation_notes: 2-4 sentences on approach, patterns, gotchas
""")


@dataclass
class Component:
    name: str
    responsibility: str
    file_path: str = ""


@dataclass
class DesignDocument:
    components: list[Component] = field(default_factory=list)
    data_models: list[str] = field(default_factory=list)
    api_contracts: list[str] = field(default_factory=list)
    implementation_notes: str = ""

    def to_markdown(self) -> str:
        lines = [
            "# Design Document",
            "",
            "## Components",
            "",
        ]
        for c in self.components:
            lines.append(f"### {c.name}")
            if c.file_path:
                lines.append(f"- **File:** `{c.file_path}`")
            lines.append(f"- **Responsibility:** {c.responsibility}")
            lines.append("")
        lines += [
            "## Data Models",
            "",
        ]
        for dm in self.data_models:
            lines.append(f"- `{dm}`")
        lines += [
            "",
            "## API Contracts",
            "",
        ]
        for contract in self.api_contracts:
            lines.append(f"- `{contract}`")
        lines += [
            "",
            "## Implementation Notes",
            "",
            self.implementation_notes,
            "",
        ]
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> "DesignDocument":
        """Parse design.md back into a DesignDocument."""
        components: list[Component] = []
        data_models: list[str] = []
        api_contracts: list[str] = []
        impl_lines: list[str] = []

        section = None
        current_comp: dict[str, str] | None = None

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("### ") and section == "components":
                if current_comp:
                    components.append(Component(**current_comp))
                current_comp = {"name": stripped[4:], "responsibility": "", "file_path": ""}
            elif stripped == "## Components":
                section = "components"
            elif stripped == "## Data Models":
                if current_comp:
                    components.append(Component(**current_comp))
                    current_comp = None
                section = "data_models"
            elif stripped == "## API Contracts":
                section = "api_contracts"
            elif stripped == "## Implementation Notes":
                section = "impl"
            elif stripped.startswith("## "):
                section = None
            elif section == "components" and current_comp:
                if stripped.startswith("- **File:**"):
                    current_comp["file_path"] = stripped.split("`")[1] if "`" in stripped else ""
                elif stripped.startswith("- **Responsibility:**"):
                    current_comp["responsibility"] = stripped.replace("- **Responsibility:**", "").strip()
            elif section == "data_models" and stripped.startswith("- `") and stripped.endswith("`"):
                data_models.append(stripped[3:-1])
            elif section == "api_contracts" and stripped.startswith("- `"):
                api_contracts.append(stripped[3:].rstrip("`"))
            elif section == "impl" and stripped:
                impl_lines.append(stripped)

        if current_comp:
            components.append(Component(**current_comp))

        return cls(
            components=components,
            data_models=data_models,
            api_contracts=api_contracts,
            implementation_notes=" ".join(impl_lines),
        )


class DesignDocGenerator:
    """Generates design.md from a SpecDocument."""

    def __init__(self, llm_client: Any | None = None) -> None:
        self._llm = llm_client

    def generate(self, spec_doc: SpecDocument, project_dir: Path) -> DesignDocument:
        """Generate design.md from spec_doc, save to project_dir."""
        doc = self._call_llm(spec_doc)
        self._save(doc, project_dir)
        return doc

    def load(self, project_dir: Path) -> DesignDocument | None:
        p = self._design_path(project_dir)
        if not p.exists():
            return None
        return DesignDocument.from_markdown(p.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------

    def _design_path(self, project_dir: Path) -> Path:
        return project_dir / _SPEC_DIR / _DESIGN_FILE

    def _call_llm(self, spec_doc: SpecDocument) -> DesignDocument:
        if self._llm is None:
            return self._offline_generate(spec_doc)

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Requirements:\n\n{spec_doc.to_markdown()}"},
        ]
        raw = self._llm(messages)
        return self._parse_json(raw)

    def _offline_generate(self, spec_doc: SpecDocument) -> DesignDocument:
        return DesignDocument(
            components=[Component(
                name=spec_doc.title,
                responsibility=spec_doc.overview[:100],
                file_path=f"src/lidco/{spec_doc.title.lower().replace(' ', '_')}.py",
            )],
            data_models=[f"{spec_doc.title.replace(' ', '')}Result: success: bool, data: str"],
            api_contracts=[f"run(input: str) -> {spec_doc.title.replace(' ', '')}Result"],
            implementation_notes="Use dataclasses for domain objects. Follow existing module patterns.",
        )

    def _parse_json(self, raw: str) -> DesignDocument:
        import json
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        data = json.loads(text)
        components = [
            Component(
                name=c.get("name", ""),
                responsibility=c.get("responsibility", ""),
                file_path=c.get("file_path", ""),
            )
            for c in data.get("components", [])
        ]
        return DesignDocument(
            components=components,
            data_models=data.get("data_models", []),
            api_contracts=data.get("api_contracts", []),
            implementation_notes=data.get("implementation_notes", ""),
        )

    def _save(self, doc: DesignDocument, project_dir: Path) -> None:
        p = self._design_path(project_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc.to_markdown(), encoding="utf-8")
        logger.info("Saved design doc to %s", p)
