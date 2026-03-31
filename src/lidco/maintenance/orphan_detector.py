"""Q148: Orphaned resource detector."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class OrphanedResource:
    path: str
    resource_type: str  # "file" | "import" | "config"
    reason: str
    suggestion: str


class OrphanDetector:
    """Detect unused files, dead configs, and orphaned imports."""

    def __init__(self) -> None:
        pass

    def detect_unused_files(
        self,
        file_list: list[str],
        import_map: dict[str, list[str]],
    ) -> list[OrphanedResource]:
        """Files in *file_list* not imported by anyone in *import_map* values."""
        imported: set[str] = set()
        for targets in import_map.values():
            imported.update(targets)
        orphans: list[OrphanedResource] = []
        for f in file_list:
            if f not in imported and f not in import_map:
                orphans.append(
                    OrphanedResource(
                        path=f,
                        resource_type="file",
                        reason="Not imported by any module",
                        suggestion=f"Consider removing {f} or adding an import",
                    )
                )
        return orphans

    def detect_dead_configs(
        self,
        config: dict,
        used_keys: set[str],
    ) -> list[OrphanedResource]:
        """Config keys in *config* not present in *used_keys*."""
        orphans: list[OrphanedResource] = []
        for key in config:
            if key not in used_keys:
                orphans.append(
                    OrphanedResource(
                        path=key,
                        resource_type="config",
                        reason=f"Config key '{key}' is not referenced",
                        suggestion=f"Remove unused config key '{key}'",
                    )
                )
        return orphans

    def detect_all(
        self,
        file_list: list[str],
        import_map: dict[str, list[str]],
        config: Optional[dict] = None,
        used_keys: Optional[set[str]] = None,
    ) -> list[OrphanedResource]:
        """Run all detection passes and return combined results."""
        results: list[OrphanedResource] = []
        results.extend(self.detect_unused_files(file_list, import_map))
        if config is not None and used_keys is not None:
            results.extend(self.detect_dead_configs(config, used_keys))
        return results

    def summary(self, orphans: list[OrphanedResource]) -> str:
        """Human-readable summary of *orphans*."""
        if not orphans:
            return "No orphaned resources detected."
        by_type: dict[str, int] = {}
        for o in orphans:
            by_type[o.resource_type] = by_type.get(o.resource_type, 0) + 1
        lines = [f"Orphaned resources: {len(orphans)}"]
        for rt, count in sorted(by_type.items()):
            lines.append(f"  {rt}: {count}")
        for o in orphans:
            lines.append(f"  [{o.resource_type}] {o.path} -- {o.reason}")
        return "\n".join(lines)
