"""Q128 — Configuration Profiles: ConfigDiff."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DiffEntry:
    key: str
    old_value: Any
    new_value: Any
    kind: str  # "added" / "removed" / "changed"


class ConfigDiff:
    """Compute and apply flat diffs between config dicts."""

    def diff(self, old: dict, new: dict) -> list[DiffEntry]:
        entries: list[DiffEntry] = []
        old_flat = self._flatten(old)
        new_flat = self._flatten(new)
        all_keys = set(old_flat) | set(new_flat)
        for key in sorted(all_keys):
            if key in old_flat and key not in new_flat:
                entries.append(DiffEntry(key, old_flat[key], None, "removed"))
            elif key not in old_flat and key in new_flat:
                entries.append(DiffEntry(key, None, new_flat[key], "added"))
            elif old_flat[key] != new_flat[key]:
                entries.append(DiffEntry(key, old_flat[key], new_flat[key], "changed"))
        return entries

    def apply(self, base: dict, entries: list[DiffEntry]) -> dict:
        result = self._flatten(base)
        for entry in entries:
            if entry.kind == "removed":
                result.pop(entry.key, None)
            elif entry.kind in ("added", "changed"):
                result[entry.key] = entry.new_value
        return self._unflatten(result)

    def summary(self, entries: list[DiffEntry]) -> str:
        added = sum(1 for e in entries if e.kind == "added")
        removed = sum(1 for e in entries if e.kind == "removed")
        changed = sum(1 for e in entries if e.kind == "changed")
        total = added + removed + changed
        return f"{total} changes: +{added} -{removed} ~{changed}"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _flatten(self, d: dict, prefix: str = "") -> dict:
        result: dict = {}
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                result.update(self._flatten(v, full_key))
            else:
                result[full_key] = v
        return result

    def _unflatten(self, flat: dict) -> dict:
        result: dict = {}
        for dotted_key, value in flat.items():
            parts = dotted_key.split(".")
            node = result
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = value
        return result
