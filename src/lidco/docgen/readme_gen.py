"""README Generator — auto-generate README.md from project structure."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class READMEConfig:
    """Configuration for README generation."""

    project_name: str
    description: str
    include_badges: bool
    include_install: bool


class READMEGenerator:
    """Generate README content from project metadata.

    Parameters
    ----------
    config:
        The README generation configuration.
    """

    def __init__(self, config: READMEConfig) -> None:
        self._config = config

    def generate(self, project_path: str) -> str:
        """Generate full README content for *project_path*."""
        lines: list[str] = []
        lines.append(f"# {self._config.project_name}")
        lines.append("")
        lines.append(self._config.description)
        lines.append("")

        if self._config.include_badges:
            lines.append(self.generate_badge("build"))
            lines.append("")

        if self._config.include_install:
            lines.append("## Installation")
            lines.append("")
            lines.append("```bash")
            lines.append(f"pip install {self._config.project_name.lower()}")
            lines.append("```")
            lines.append("")

        detected = self.detect_sections(project_path)
        for section in detected:
            lines.append(f"## {section}")
            lines.append("")

        return "\n".join(lines)

    def detect_sections(self, path: str) -> tuple[str, ...]:
        """Detect recommended sections based on project contents."""
        sections: list[str] = []
        try:
            entries = os.listdir(path)
        except OSError:
            return ()
        if any(f in entries for f in ("tests", "test")):
            sections.append("Testing")
        if any(f in entries for f in ("LICENSE", "LICENSE.md", "LICENSE.txt")):
            sections.append("License")
        if any(f in entries for f in ("docs", "doc")):
            sections.append("Documentation")
        if "CONTRIBUTING.md" in entries:
            sections.append("Contributing")
        return tuple(sections)

    def generate_badge(self, badge_type: str) -> str:
        """Generate a markdown badge string for *badge_type*."""
        name = self._config.project_name.lower()
        badges = {
            "build": f"![Build](https://img.shields.io/badge/build-passing-green)",
            "version": f"![Version](https://img.shields.io/badge/version-0.1.0-blue)",
            "license": f"![License](https://img.shields.io/badge/license-MIT-yellow)",
            "python": f"![Python](https://img.shields.io/badge/python-3.10+-blue)",
        }
        return badges.get(badge_type, f"![{badge_type}](https://img.shields.io/badge/{badge_type}-unknown-grey)")


__all__ = ["READMEConfig", "READMEGenerator"]
