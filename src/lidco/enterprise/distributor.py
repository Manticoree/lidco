"""Config distribution with canary rollout and version tracking."""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConfigVersion:
    """Immutable snapshot of a configuration version."""

    version: int
    config: dict
    created_at: float
    author: str = "system"
    description: str = ""


@dataclass
class RolloutStatus:
    """Tracks rollout progress across fleet targets."""

    version: int
    target_count: int
    applied_count: int = 0
    failed_count: int = 0
    status: str = "pending"


class ConfigDistributor:
    """Push config to fleet with canary rollout, rollback, and version tracking."""

    def __init__(self) -> None:
        self._versions: list[ConfigVersion] = []
        self._rollouts: dict[int, RolloutStatus] = {}
        self._applied: dict[str, int] = {}  # target -> version
        self._next_version: int = 1

    def publish(
        self,
        config: dict,
        author: str = "system",
        description: str = "",
    ) -> ConfigVersion:
        """Publish a new config version."""
        ver = ConfigVersion(
            version=self._next_version,
            config=copy.deepcopy(config),
            created_at=time.time(),
            author=author,
            description=description,
        )
        self._versions.append(ver)
        self._next_version += 1
        return ver

    def versions(self) -> list[ConfigVersion]:
        """Return all published versions."""
        return list(self._versions)

    def get_version(self, version: int) -> ConfigVersion | None:
        """Return a specific version or None."""
        for v in self._versions:
            if v.version == version:
                return v
        return None

    def diff(self, v1: int, v2: int) -> dict:
        """Compute keys added/removed/changed between two versions."""
        cv1 = self.get_version(v1)
        cv2 = self.get_version(v2)
        if cv1 is None or cv2 is None:
            return {"added": [], "removed": [], "changed": []}

        c1 = cv1.config
        c2 = cv2.config
        k1 = set(c1.keys())
        k2 = set(c2.keys())

        added = sorted(k2 - k1)
        removed = sorted(k1 - k2)
        changed = sorted(k for k in k1 & k2 if c1[k] != c2[k])
        return {"added": added, "removed": removed, "changed": changed}

    def rollout(
        self,
        version: int,
        targets: list[str],
        canary_pct: int = 0,
    ) -> RolloutStatus:
        """Roll out a version to targets, optionally with canary percentage."""
        cv = self.get_version(version)
        if cv is None:
            status = RolloutStatus(version=version, target_count=0, status="pending")
            return status

        status = RolloutStatus(
            version=version,
            target_count=len(targets),
            status="in_progress",
        )

        if canary_pct > 0:
            canary_count = max(1, len(targets) * canary_pct // 100)
            canary_targets = targets[:canary_count]
            for t in canary_targets:
                if self.apply_to(t, version):
                    status.applied_count += 1
                else:
                    status.failed_count += 1
        else:
            for t in targets:
                if self.apply_to(t, version):
                    status.applied_count += 1
                else:
                    status.failed_count += 1

        if status.applied_count == status.target_count:
            status.status = "completed"

        self._rollouts[version] = status
        return status

    def apply_to(self, target: str, version: int) -> bool:
        """Simulate applying a version to a target. Returns True on success."""
        cv = self.get_version(version)
        if cv is None:
            return False
        self._applied[target] = version
        return True

    def rollback(self, version: int) -> RolloutStatus | None:
        """Mark a rollout as rolled back."""
        status = self._rollouts.get(version)
        if status is None:
            return None
        status.status = "rolled_back"
        return status

    def current_version(self) -> ConfigVersion | None:
        """Return the latest published version."""
        if not self._versions:
            return None
        return self._versions[-1]

    def summary(self) -> dict:
        """Return summary of distributor state."""
        current = self.current_version()
        return {
            "total_versions": len(self._versions),
            "current_version": current.version if current else None,
            "total_rollouts": len(self._rollouts),
            "applied_targets": len(self._applied),
        }
