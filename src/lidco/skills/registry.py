"""Skill registry — Tasks 294, 297.

Discovers skills from:
  1. ``~/.lidco/skills/``   — global personal library
  2. ``.lidco/skills/``     — project-local skills (override global)

Supports ``.md``, ``.yaml``, and ``.yml`` skill files.

Usage::

    registry = SkillRegistry()
    registry.load()
    skill = registry.get("review")
    all_skills = registry.list_skills()
"""

from __future__ import annotations

import logging
from pathlib import Path

from lidco.skills.skill import Skill, parse_skill_file

logger = logging.getLogger(__name__)

_SKILL_EXTENSIONS = ("*.md", "*.yaml", "*.yml")


class SkillRegistry:
    """Loads and provides access to skill definitions.

    Args:
        project_dir: Project root. Defaults to cwd.
        extra_dirs: Additional directories to scan.
    """

    def __init__(
        self,
        project_dir: Path | None = None,
        extra_dirs: list[Path] | None = None,
    ) -> None:
        self._project_dir = project_dir or Path.cwd()
        self._skills: dict[str, Skill] = {}
        self._search_dirs: list[Path] = [
            Path.home() / ".lidco" / "skills",          # global (Task 297)
            self._project_dir / ".lidco" / "skills",    # project-local
        ]
        if extra_dirs:
            self._search_dirs.extend(extra_dirs)

    def load(self) -> int:
        """Scan skill directories and load all valid skill files.

        Project-local skills override global ones with the same name.
        Returns the number of skills loaded.
        """
        self._skills.clear()
        loaded = 0
        for directory in self._search_dirs:
            if not directory.is_dir():
                continue
            files: list[Path] = []
            for pattern in _SKILL_EXTENSIONS:
                files.extend(directory.glob(pattern))
            for path in sorted(files):
                try:
                    skill = parse_skill_file(path)
                    self._skills[skill.name] = skill
                    loaded += 1
                    logger.debug("Loaded skill '%s' from %s", skill.name, path)
                except Exception as exc:
                    logger.warning("Failed to load skill from %s: %s", path, exc)
        logger.info("SkillRegistry: %d skill(s) loaded", loaded)
        return loaded

    def get(self, name: str) -> Skill | None:
        """Return a skill by name, or None."""
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        """Return all loaded skills sorted by name."""
        return sorted(self._skills.values(), key=lambda s: s.name)

    def names(self) -> list[str]:
        """Return sorted list of skill names."""
        return sorted(self._skills.keys())

    def register(self, skill: Skill) -> None:
        """Manually register a skill (e.g., from tests or dynamic creation)."""
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        """Remove a skill by name. Returns True if it existed."""
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def reload(self) -> int:
        """Re-scan directories and reload skills."""
        return self.load()
