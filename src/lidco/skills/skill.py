"""Skill definition — Task 293.

A Skill is a reusable workflow stored as a Markdown file with YAML frontmatter.

File format (.lidco/skills/review.md)::

    ---
    name: review
    description: Review code for quality and security
    version: 1.0
    requires: [git]
    context: src/
    scripts:
      pre: echo "Starting review..."
    ---
    Review the following code for: quality, security, edge cases.
    Focus on: {args}

The prompt body (below ``---``) is a template where ``{args}`` is replaced
with whatever the user passed after the skill name.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


@dataclass
class Skill:
    """A loaded skill definition."""

    name: str
    description: str = ""
    prompt: str = ""         # template; {args} substituted at runtime
    context: str = ""        # files/dirs to inject as context
    version: str = "1.0"
    requires: list[str] = field(default_factory=list)   # CLI tools required
    scripts: dict[str, str] = field(default_factory=dict)  # pre/post hooks
    path: str = ""           # source file path

    def render(self, args: str = "") -> str:
        """Return the final prompt with ``{args}`` substituted."""
        return self.prompt.replace("{args}", args).strip()

    def check_requirements(self) -> list[str]:
        """Return list of missing required tools (empty = all satisfied)."""
        missing: list[str] = []
        for tool in self.requires:
            if not shutil.which(tool):
                missing.append(tool)
        return missing

    def run_script(self, hook: str) -> tuple[bool, str]:
        """Run a pre/post script hook. Returns (success, output)."""
        cmd = self.scripts.get(hook)
        if not cmd:
            return True, ""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            output = (result.stdout + result.stderr).strip()
            return result.returncode == 0, output
        except subprocess.TimeoutExpired:
            return False, f"Script '{hook}' timed out"
        except Exception as exc:
            return False, str(exc)


def parse_skill_file(path: Path) -> Skill:
    """Parse a SKILL.md file into a Skill object.

    Supports both pure YAML (.yaml/.yml) and Markdown+frontmatter (.md).

    Raises:
        ValueError: if required ``name`` field is missing.
    """
    text = path.read_text(encoding="utf-8")

    if path.suffix == ".md":
        m = _FRONTMATTER_RE.match(text)
        if not m:
            raise ValueError(f"No YAML frontmatter in {path}")
        data: dict[str, Any] = yaml.safe_load(m.group(1)) or {}
        body = m.group(2).strip()
        if body and not data.get("prompt"):
            data["prompt"] = body
    else:
        data = yaml.safe_load(text) or {}

    name = data.get("name") or path.stem
    if not name:
        raise ValueError(f"Skill file {path} missing 'name' field")

    requires = data.get("requires") or []
    if isinstance(requires, str):
        requires = [r.strip() for r in requires.split(",")]

    return Skill(
        name=str(name),
        description=str(data.get("description", "")),
        prompt=str(data.get("prompt", "")),
        context=str(data.get("context", "")),
        version=str(data.get("version", "1.0")),
        requires=list(requires),
        scripts=dict(data.get("scripts") or {}),
        path=str(path),
    )
