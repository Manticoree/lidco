"""Prompt template library — Cursor Prompt Files / Continue.dev parity.

Templates are Markdown files stored in:
  - `<project>/.lidco/prompts/*.md`   (project-local, highest priority)
  - `~/.lidco/prompts/*.md`           (global / user-level)

Project templates override global ones with the same stem name.
Variables use ``{{variable_name}}`` or ``{{ variable_name }}`` syntax.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# B7: Allow optional whitespace around variable names ({{ var }} or {{var}})
_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@dataclass
class PromptTemplate:
    """A single prompt template loaded from disk."""

    name: str
    content: str
    variables: list[str]
    source_path: str


@dataclass
class RenderResult:
    """Result of rendering a template with variable substitution."""

    name: str
    rendered: str
    missing_vars: list[str] = field(default_factory=list)
    # B1: Distinguish "template not found" from "template found but empty"
    found: bool = True


class PromptTemplateLibrary:
    """Discover, load, render, and save prompt templates.

    Usage::

        lib = PromptTemplateLibrary()
        for tpl in lib.list():
            print(tpl.name)
        result = lib.render("fix-bug", {"language": "Python"})
        if result.found:
            print(result.rendered)
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root)
        self._project_dir = self.project_root / ".lidco" / "prompts"
        self._global_dir = Path.home() / ".lidco" / "prompts"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list(self) -> list[PromptTemplate]:
        """Return all templates (project overrides global by stem name)."""
        templates: dict[str, PromptTemplate] = {}
        # Load global first, then project (project wins)
        for path in self._discover(self._global_dir):
            tpl = self._load_path(path)
            if tpl is not None:  # B8: skip unreadable files
                templates[tpl.name] = tpl
        for path in self._discover(self._project_dir):
            tpl = self._load_path(path)
            if tpl is not None:  # B8: skip unreadable files
                templates[tpl.name] = tpl
        return sorted(templates.values(), key=lambda t: t.name)

    def load(self, name: str) -> PromptTemplate | None:
        """Return the template with *name*, or None if not found."""
        # Project takes priority
        for search_dir in (self._project_dir, self._global_dir):
            path = search_dir / f"{name}.md"
            if path.exists():
                return self._load_path(path)  # may return None on read error
        return None

    def render(
        self, name: str, variables: dict[str, str] | None = None
    ) -> RenderResult:
        """Render template *name* substituting *variables*.

        Variables missing from *variables* are left as-is and reported in
        ``RenderResult.missing_vars``.  ``RenderResult.found`` is False when
        the template does not exist.
        """
        tpl = self.load(name)
        if tpl is None:
            # B1: mark as not found so callers can distinguish from empty template
            return RenderResult(name=name, rendered="", found=False)

        vars_map = variables or {}
        missing: list[str] = []

        # B7: Use regex substitution so {{ var }} and {{var}} both work
        def _replace(m: re.Match) -> str:
            var = m.group(1)
            if var in vars_map:
                return vars_map[var]
            missing.append(var)
            return m.group(0)  # leave original placeholder intact

        rendered = _VAR_RE.sub(_replace, tpl.content)
        return RenderResult(name=name, rendered=rendered, missing_vars=missing, found=True)

    def save(self, name: str, content: str) -> PromptTemplate:
        """Save *content* as template *name* to the project prompts directory."""
        self._project_dir.mkdir(parents=True, exist_ok=True)
        path = self._project_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        tpl = self._load_path(path)
        if tpl is None:
            raise OSError(f"Failed to read back saved template: {path}")
        return tpl

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _discover(self, directory: Path) -> list[Path]:
        if not directory.exists():
            return []
        return sorted(directory.glob("*.md"))

    def _load_path(self, path: Path) -> PromptTemplate | None:
        # B8: Handle file read errors gracefully
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        variables = self._extract_variables(content)
        return PromptTemplate(
            name=path.stem,
            content=content,
            variables=variables,
            source_path=str(path),
        )

    def _extract_variables(self, content: str) -> list[str]:
        """Return unique variable names found in *content* preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for match in _VAR_RE.finditer(content):
            var = match.group(1)
            if var not in seen:
                seen.add(var)
                result.append(var)
        return result
