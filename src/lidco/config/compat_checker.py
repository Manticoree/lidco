"""Q144 — Configuration Migration & Versioning: CompatChecker."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CompatIssue:
    """A single compatibility issue."""

    field: str
    issue_type: str  # "removed" / "renamed" / "type_changed" / "deprecated"
    message: str
    severity: str  # "error" / "warning"


@dataclass
class CompatResult:
    """Aggregate compatibility check result."""

    compatible: bool
    issues: list[CompatIssue] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class CompatChecker:
    """Check config dicts against compatibility rules."""

    def __init__(self) -> None:
        self._removed: list[tuple[str, str, Optional[str]]] = []  # (field, since, alt)
        self._renamed: list[tuple[str, str, str]] = []  # (old, new, since)
        self._deprecated: list[tuple[str, str]] = []  # (field, message)

    def add_removed(self, field: str, since_version: str, alternative: str | None = None) -> None:
        self._removed.append((field, since_version, alternative))

    def add_renamed(self, old_field: str, new_field: str, since_version: str) -> None:
        self._renamed.append((old_field, new_field, since_version))

    def add_deprecated(self, field: str, message: str) -> None:
        self._deprecated.append((field, message))

    def check(self, data: dict) -> CompatResult:
        flat = self._flatten(data)
        issues: list[CompatIssue] = []
        suggestions: list[str] = []

        for fld, since, alt in self._removed:
            if fld in flat:
                msg = f"Field '{fld}' was removed in {since}."
                if alt:
                    msg += f" Use '{alt}' instead."
                    suggestions.append(f"Replace '{fld}' with '{alt}'.")
                issues.append(CompatIssue(field=fld, issue_type="removed", message=msg, severity="error"))

        for old, new, since in self._renamed:
            if old in flat:
                msg = f"Field '{old}' was renamed to '{new}' in {since}."
                suggestions.append(f"Rename '{old}' to '{new}'.")
                issues.append(CompatIssue(field=old, issue_type="renamed", message=msg, severity="warning"))

        for fld, message in self._deprecated:
            if fld in flat:
                issues.append(CompatIssue(field=fld, issue_type="deprecated", message=message, severity="warning"))

        compatible = not any(i.severity == "error" for i in issues)
        return CompatResult(compatible=compatible, issues=issues, suggestions=suggestions)

    def auto_fix(self, data: dict) -> tuple[dict, list[str]]:
        """Apply automatic fixes (renames). Returns (fixed_data, actions)."""
        result = copy.deepcopy(data)
        actions: list[str] = []
        flat = self._flatten(result)

        for old, new, _since in self._renamed:
            if old in flat:
                self._set_nested(result, new, flat[old])
                self._del_nested(result, old)
                actions.append(f"Renamed '{old}' -> '{new}'.")

        for fld, _since, _alt in self._removed:
            if fld in self._flatten(result):
                self._del_nested(result, fld)
                actions.append(f"Removed deprecated field '{fld}'.")

        return result, actions

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _flatten(d: dict, prefix: str = "") -> dict:
        result: dict = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                result.update(CompatChecker._flatten(v, key))
            else:
                result[key] = v
        return result

    @staticmethod
    def _set_nested(d: dict, dotted: str, value: object) -> None:
        parts = dotted.split(".")
        node = d
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = value

    @staticmethod
    def _del_nested(d: dict, dotted: str) -> None:
        parts = dotted.split(".")
        node = d
        for p in parts[:-1]:
            if p not in node or not isinstance(node[p], dict):
                return
            node = node[p]
        node.pop(parts[-1], None)
