"""Workspace profile support for LIDCO — Task 385.

A *profile* is a named YAML file that overrides config fields (model, agents,
permissions, etc.) for a specific project context (frontend, backend, etc.).

Profile resolution order (last wins):
  1. Built-in profile (hardcoded defaults)
  2. ``~/.lidco/profiles/<name>.yaml``   (user-global)
  3. ``.lidco/profiles/<name>.yaml``     (project-local)

Usage::

    loader = ProfileLoader()
    data = loader.load("frontend", project_dir=Path("."))
    names = loader.list_profiles(project_dir=Path("."))
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in profile templates
# ---------------------------------------------------------------------------

_BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "frontend": {
        "description": "Frontend / UI development",
        "agents": {"default": "coder", "auto_review": True, "auto_plan": True},
        "llm": {"default_model": "openai/glm-4.7", "temperature": 0.2},
        "focus": ["src/", "public/", "*.tsx", "*.ts", "*.css"],
    },
    "backend": {
        "description": "Backend / API development",
        "agents": {"default": "coder", "auto_review": True, "auto_plan": True},
        "llm": {"default_model": "openai/glm-4.7", "temperature": 0.1},
        "focus": ["src/", "api/", "*.py", "*.go"],
    },
    "data": {
        "description": "Data science / ML",
        "agents": {"default": "coder", "auto_review": False, "auto_plan": False},
        "llm": {"default_model": "openai/glm-4.7", "temperature": 0.3},
        "focus": ["notebooks/", "data/", "*.ipynb", "*.py"],
    },
    "devops": {
        "description": "DevOps / infrastructure",
        "agents": {"default": "architect", "auto_review": True, "auto_plan": True},
        "llm": {"default_model": "openai/glm-4.7", "temperature": 0.1},
        "focus": [".github/", "Dockerfile", "*.yaml", "*.yml"],
    },
    "security": {
        "description": "Security-focused review",
        "agents": {"default": "security", "auto_review": True, "auto_plan": True},
        "llm": {"default_model": "openai/glm-4.7", "temperature": 0.05},
        "focus": ["src/", "auth/", "*.py"],
    },
}


class ProfileLoader:
    """Load workspace profiles from built-ins and YAML files."""

    @staticmethod
    def _global_dir() -> Path:
        return Path.home() / ".lidco" / "profiles"

    @staticmethod
    def _project_dir(project_dir: Path) -> Path:
        return project_dir / ".lidco" / "profiles"

    def load(self, name: str, project_dir: Path | None = None) -> dict[str, Any] | None:
        """Load a profile by name.

        Merges built-in → global → project-local (later keys win).
        Returns ``None`` if the profile is not found anywhere.
        """
        data: dict[str, Any] = {}
        found = False

        # 1. Built-in
        if name in _BUILTIN_PROFILES:
            data = dict(_BUILTIN_PROFILES[name])
            found = True

        # 2. Global user profile (~/.lidco/profiles/<name>.yaml)
        global_path = self._global_dir() / f"{name}.yaml"
        if not global_path.exists():
            global_path = self._global_dir() / f"{name}.yml"
        if global_path.exists():
            loaded = self._load_yaml(global_path)
            if loaded is not None:
                data = {**data, **loaded}
                found = True

        # 3. Project-local profile (.lidco/profiles/<name>.yaml)
        if project_dir is not None:
            local_path = self._project_dir(project_dir) / f"{name}.yaml"
            if not local_path.exists():
                local_path = self._project_dir(project_dir) / f"{name}.yml"
            if local_path.exists():
                loaded = self._load_yaml(local_path)
                if loaded is not None:
                    data = {**data, **loaded}
                    found = True

        if not found:
            return None
        data["name"] = name
        return data

    def list_profiles(self, project_dir: Path | None = None) -> list[str]:
        """Return all available profile names (built-ins + discovered YAML files)."""
        names: set[str] = set(_BUILTIN_PROFILES.keys())

        for search_dir in [self._global_dir(), *(
            [self._project_dir(project_dir)] if project_dir is not None else []
        )]:
            if search_dir.exists():
                for p in search_dir.glob("*.yaml"):
                    names.add(p.stem)
                for p in search_dir.glob("*.yml"):
                    names.add(p.stem)

        return sorted(names)

    def save(self, name: str, data: dict[str, Any], project_dir: Path | None = None) -> Path:
        """Save a profile to the project-local (or global) profiles directory."""
        import yaml as _yaml

        target_dir = (
            self._project_dir(project_dir) if project_dir is not None else self._global_dir()
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / f"{name}.yaml"
        path.write_text(_yaml.dump(data, allow_unicode=True), encoding="utf-8")
        logger.info("ProfileLoader: saved profile '%s' to %s", name, path)
        return path

    def delete(self, name: str, project_dir: Path | None = None) -> bool:
        """Delete a project-local profile. Returns True if it existed."""
        if project_dir is not None:
            for suffix in (".yaml", ".yml"):
                p = self._project_dir(project_dir) / f"{name}{suffix}"
                if p.exists():
                    p.unlink()
                    return True
        return False

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any] | None:
        try:
            import yaml as _yaml
            data = _yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return None
        except Exception as exc:
            logger.warning("ProfileLoader: failed to load '%s': %s", path, exc)
            return None
