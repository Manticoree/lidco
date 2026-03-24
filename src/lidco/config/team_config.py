"""Team configuration loader — Cursor Teams / shared config parity.

Loads `.lidco/team.yaml` (project-shared, committed to git) and
`.lidco/user.yaml` (personal overrides, gitignored).  The two are merged
so personal settings always win over team defaults.

Requires PyYAML when YAML files are present; gracefully degrades to empty
config when the library is not installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


try:
    import yaml as _yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    _yaml = None  # type: ignore[assignment]


@dataclass
class TeamConfig:
    """Parsed team-level configuration."""

    model: str = ""
    tools: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    permissions: dict[str, bool] = field(default_factory=dict)
    members: list[str] = field(default_factory=list)


@dataclass
class MergedConfig:
    """Combined team + personal configuration."""

    team: TeamConfig
    personal: dict[str, Any]
    resolved: dict[str, Any]  # team defaults merged with personal overrides


class TeamConfigLoader:
    """Load, merge, and validate team + personal LIDCO configuration.

    Usage::

        loader = TeamConfigLoader()
        merged = loader.load()
        print(merged.resolved.get("model"))
    """

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root)
        self._team_path = self.project_root / ".lidco" / "team.yaml"
        self._personal_path = self.project_root / ".lidco" / "user.yaml"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_team(self) -> TeamConfig | None:
        """Load and parse team.yaml; return None if file does not exist."""
        if not self._team_path.exists():
            return None
        raw = self._read_yaml(self._team_path)
        # B2: _read_yaml now always returns dict (never None)
        return TeamConfig(
            model=raw.get("model", ""),
            tools=list(raw.get("tools", [])),
            rules=list(raw.get("rules", [])),
            permissions=dict(raw.get("permissions", {})),
            members=list(raw.get("members", [])),
        )

    def load_personal(self) -> dict[str, Any]:
        """Load user.yaml; return empty dict if file does not exist."""
        if not self._personal_path.exists():
            return {}
        return self._read_yaml(self._personal_path)

    def merge(self, team: TeamConfig, personal: dict[str, Any]) -> MergedConfig:
        """Merge *team* defaults with *personal* overrides.

        Scalar and list values: personal wins (replaces team entirely).
        Dict values (e.g. ``permissions``): deep-merged so personal entries
        selectively override individual keys without losing team-level keys.
        """
        base: dict[str, Any] = {
            "model": team.model,
            "tools": list(team.tools),
            "rules": list(team.rules),
            "permissions": dict(team.permissions),
            "members": list(team.members),
        }
        # B3: deep-merge nested dicts so personal.permissions doesn't wipe team ones
        resolved = _deep_merge(base, personal)
        return MergedConfig(team=team, personal=personal, resolved=resolved)

    def validate(self, config: TeamConfig) -> list[str]:
        """Return a list of validation error strings (empty = valid)."""
        errors: list[str] = []
        if config.model and not isinstance(config.model, str):
            errors.append("'model' must be a string")
        if not isinstance(config.tools, list):
            errors.append("'tools' must be a list")
        else:
            # B10: validate list element types
            for i, item in enumerate(config.tools):
                if not isinstance(item, str):
                    errors.append(f"'tools[{i}]' must be a string, got {type(item).__name__}")
        if not isinstance(config.rules, list):
            errors.append("'rules' must be a list")
        else:
            for i, item in enumerate(config.rules):
                if not isinstance(item, str):
                    errors.append(f"'rules[{i}]' must be a string, got {type(item).__name__}")
        if not isinstance(config.permissions, dict):
            errors.append("'permissions' must be a mapping")
        if not isinstance(config.members, list):
            errors.append("'members' must be a list")
        else:
            for i, item in enumerate(config.members):
                if not isinstance(item, str):
                    errors.append(f"'members[{i}]' must be a string, got {type(item).__name__}")
        if isinstance(config.permissions, dict):
            for perm_key, perm_val in config.permissions.items():
                if not isinstance(perm_val, bool):
                    errors.append(
                        f"'permissions.{perm_key}' must be a boolean, got {type(perm_val).__name__}"
                    )
        return errors

    def load(self) -> MergedConfig:
        """Load team + personal configs and return a merged result."""
        team = self.load_team() or TeamConfig()
        personal = self.load_personal()
        return self.merge(team, personal)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_yaml(self, path: Path) -> dict[str, Any]:
        # B2: Always return a dict — never None — so callers don't need None checks
        if _yaml is None:
            return {}
        try:
            text = path.read_text(encoding="utf-8")
            data = _yaml.safe_load(text)
            if isinstance(data, dict):
                return data
            return {}
        except Exception:  # noqa: BLE001
            # Parse errors or I/O errors → treat as empty config
            return {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict merging *override* into *base*.

    Scalar/list values: override wins.
    Dict values: recursively merged so individual keys can be overridden.
    """
    result: dict[str, Any] = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
