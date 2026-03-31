"""Q144 — Configuration Migration & Versioning: ConfigMigrator."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

from lidco.config.config_version import ConfigVersion


@dataclass
class MigrationStep:
    """A single migration from one version to another."""

    from_version: str
    to_version: str
    description: str
    migrate_fn: Callable[[dict], dict]


@dataclass
class MigrationResult:
    """Outcome of a migration run."""

    success: bool
    from_version: str
    to_version: str
    steps_applied: int
    data: dict
    errors: list[str] = field(default_factory=list)


class ConfigMigrator:
    """Apply ordered migration steps to upgrade config data."""

    def __init__(self) -> None:
        self._steps: list[MigrationStep] = []
        self._cv = ConfigVersion()

    def add_step(
        self,
        from_v: str,
        to_v: str,
        description: str,
        migrate_fn: Callable[[dict], dict],
    ) -> None:
        self._steps.append(MigrationStep(from_v, to_v, description, migrate_fn))

    def migration_path(self, from_v: str, to_v: str) -> list[MigrationStep]:
        """Find an ordered chain of steps from *from_v* to *to_v*."""
        # Build adjacency
        adj: dict[str, list[MigrationStep]] = {}
        for s in self._steps:
            adj.setdefault(s.from_version, []).append(s)

        # BFS
        visited: set[str] = set()
        queue: list[tuple[str, list[MigrationStep]]] = [(from_v, [])]
        while queue:
            current, path = queue.pop(0)
            if current == to_v:
                return path
            if current in visited:
                continue
            visited.add(current)
            for step in adj.get(current, []):
                queue.append((step.to_version, path + [step]))
        return []

    def can_migrate(self, from_v: str, to_v: str) -> bool:
        if from_v == to_v:
            return True
        return len(self.migration_path(from_v, to_v)) > 0

    def migrate(self, data: dict, target_version: str) -> MigrationResult:
        """Apply migration chain to *data*."""
        current_v = self._cv.get_version(data)
        if current_v is None:
            current_v = "0.0.0"
        if current_v == target_version:
            return MigrationResult(
                success=True,
                from_version=current_v,
                to_version=target_version,
                steps_applied=0,
                data=dict(data),
            )
        path = self.migration_path(current_v, target_version)
        if not path:
            return MigrationResult(
                success=False,
                from_version=current_v,
                to_version=target_version,
                steps_applied=0,
                data=dict(data),
                errors=[f"No migration path from {current_v} to {target_version}"],
            )
        result_data = dict(data)
        steps_done = 0
        errors: list[str] = []
        for step in path:
            try:
                result_data = step.migrate_fn(result_data)
                steps_done += 1
            except Exception as exc:
                errors.append(f"Step {step.from_version}->{step.to_version}: {exc}")
                return MigrationResult(
                    success=False,
                    from_version=current_v,
                    to_version=target_version,
                    steps_applied=steps_done,
                    data=result_data,
                    errors=errors,
                )
        # Stamp new version
        result_data[ConfigVersion.VERSION_KEY] = target_version
        return MigrationResult(
            success=True,
            from_version=current_v,
            to_version=target_version,
            steps_applied=steps_done,
            data=result_data,
        )

    def dry_run(self, data: dict, target_version: str) -> MigrationResult:
        """Preview migration without modifying *data*."""
        return self.migrate(copy.deepcopy(data), target_version)
