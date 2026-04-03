"""API endpoint diffing and compatibility checking."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.api_intel.extractor import Endpoint


@dataclass(frozen=True)
class DiffEntry:
    """A single diff entry between two API versions."""

    type: str  # "added", "removed", "changed"
    path: str
    details: str
    breaking: bool = False


class APIDiff:
    """Diff two sets of API endpoints."""

    def diff(
        self,
        old_endpoints: list[Endpoint],
        new_endpoints: list[Endpoint],
    ) -> list[DiffEntry]:
        """Compute differences between old and new endpoint lists."""
        old_map: dict[tuple[str, str], Endpoint] = {
            (ep.method, ep.path): ep for ep in old_endpoints
        }
        new_map: dict[tuple[str, str], Endpoint] = {
            (ep.method, ep.path): ep for ep in new_endpoints
        }

        entries: list[DiffEntry] = []

        # Removed endpoints
        for key in old_map:
            if key not in new_map:
                entries = [*entries, DiffEntry(
                    type="removed",
                    path=f"{key[0]} {key[1]}",
                    details="Endpoint removed",
                    breaking=True,
                )]

        # Added endpoints
        for key in new_map:
            if key not in old_map:
                entries = [*entries, DiffEntry(
                    type="added",
                    path=f"{key[0]} {key[1]}",
                    details="Endpoint added",
                    breaking=False,
                )]

        # Changed endpoints
        for key in old_map:
            if key in new_map:
                old_ep = old_map[key]
                new_ep = new_map[key]
                changes = self._compare_endpoints(old_ep, new_ep)
                for change in changes:
                    entries = [*entries, change]

        return entries

    @staticmethod
    def _compare_endpoints(old: Endpoint, new: Endpoint) -> list[DiffEntry]:
        """Compare two endpoints with the same method+path."""
        changes: list[DiffEntry] = []
        label = f"{old.method} {old.path}"

        # Check params removed (breaking)
        old_param_names = {p["name"] for p in old.params}
        new_param_names = {p["name"] for p in new.params}
        removed_params = old_param_names - new_param_names
        added_params = new_param_names - old_param_names

        if removed_params:
            changes = [*changes, DiffEntry(
                type="changed",
                path=label,
                details=f"Parameter(s) removed: {', '.join(sorted(removed_params))}",
                breaking=True,
            )]

        if added_params:
            changes = [*changes, DiffEntry(
                type="changed",
                path=label,
                details=f"Parameter(s) added: {', '.join(sorted(added_params))}",
                breaking=False,
            )]

        # Check return type change
        if old.return_type != new.return_type:
            changes = [*changes, DiffEntry(
                type="changed",
                path=label,
                details=f"Return type changed: {old.return_type} -> {new.return_type}",
                breaking=True,
            )]

        # Check description change (non-breaking)
        if old.description != new.description and new.description:
            changes = [*changes, DiffEntry(
                type="changed",
                path=label,
                details=f"Description changed",
                breaking=False,
            )]

        return changes

    @staticmethod
    def breaking_changes(entries: list[DiffEntry]) -> list[DiffEntry]:
        """Filter to only breaking changes."""
        return [e for e in entries if e.breaking]

    @staticmethod
    def summary(entries: list[DiffEntry]) -> str:
        """Return a human-readable summary of diff entries."""
        if not entries:
            return "No changes detected."
        breaking = [e for e in entries if e.breaking]
        lines = [f"{len(entries)} change(s) detected ({len(breaking)} breaking):"]
        for e in entries:
            flag = " [BREAKING]" if e.breaking else ""
            lines.append(f"  [{e.type}] {e.path}: {e.details}{flag}")
        return "\n".join(lines)

    def is_compatible(
        self,
        old: list[Endpoint],
        new: list[Endpoint],
    ) -> bool:
        """Check if new endpoints are backward-compatible with old."""
        entries = self.diff(old, new)
        return len(self.breaking_changes(entries)) == 0
