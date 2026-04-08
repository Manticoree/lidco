"""Env Comparator — compare environments, detect drift.

Config diff, version diff, drift detection, sync recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lidco.envmgmt.provisioner import Environment


class DiffKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


@dataclass(frozen=True)
class ConfigDiff:
    """Single config key difference."""

    key: str
    kind: DiffKind
    left_value: Any = None
    right_value: Any = None


@dataclass(frozen=True)
class DriftItem:
    """A detected drift between environments."""

    key: str
    expected: Any
    actual: Any
    severity: str = "medium"  # low, medium, high


@dataclass(frozen=True)
class SyncRecommendation:
    """Recommendation to bring environments in sync."""

    action: str
    key: str
    value: Any
    reason: str


@dataclass
class ComparisonResult:
    """Full comparison between two environments."""

    left_name: str
    right_name: str
    config_diffs: list[ConfigDiff] = field(default_factory=list)
    resource_diffs: list[ConfigDiff] = field(default_factory=list)
    tag_diffs: list[ConfigDiff] = field(default_factory=list)
    drift_items: list[DriftItem] = field(default_factory=list)
    recommendations: list[SyncRecommendation] = field(default_factory=list)

    @property
    def has_diffs(self) -> bool:
        return bool(self.config_diffs or self.resource_diffs or self.tag_diffs)

    @property
    def drift_count(self) -> int:
        return len(self.drift_items)


class EnvComparator:
    """Compare two environments and detect drift."""

    # Keys whose differences are considered high-severity drift
    HIGH_SEVERITY_KEYS: set[str] = {"replicas", "debug", "log_level", "version"}

    def compare(self, left: Environment, right: Environment) -> ComparisonResult:
        """Full comparison of two environments."""
        result = ComparisonResult(left_name=left.name, right_name=right.name)
        result.config_diffs = self._diff_dicts(left.config, right.config)
        result.resource_diffs = self._diff_dicts(left.resources, right.resources)
        result.tag_diffs = self._diff_dicts(left.tags, right.tags)
        result.drift_items = self._detect_drift(left, right)
        result.recommendations = self._generate_recommendations(result)
        return result

    # -- Dict diffing ---------------------------------------------------------

    @staticmethod
    def _diff_dicts(
        left: dict[str, Any], right: dict[str, Any]
    ) -> list[ConfigDiff]:
        diffs: list[ConfigDiff] = []
        all_keys = sorted(set(left) | set(right))
        for key in all_keys:
            in_left = key in left
            in_right = key in right
            if in_left and not in_right:
                diffs.append(ConfigDiff(key=key, kind=DiffKind.REMOVED, left_value=left[key]))
            elif not in_left and in_right:
                diffs.append(ConfigDiff(key=key, kind=DiffKind.ADDED, right_value=right[key]))
            elif left[key] != right[key]:
                diffs.append(
                    ConfigDiff(
                        key=key,
                        kind=DiffKind.CHANGED,
                        left_value=left[key],
                        right_value=right[key],
                    )
                )
        return diffs

    # -- Drift detection ------------------------------------------------------

    def _detect_drift(self, left: Environment, right: Environment) -> list[DriftItem]:
        items: list[DriftItem] = []
        for diff in self._diff_dicts(left.config, right.config):
            if diff.kind == DiffKind.CHANGED:
                severity = (
                    "high" if diff.key in self.HIGH_SEVERITY_KEYS else "medium"
                )
                items.append(
                    DriftItem(
                        key=diff.key,
                        expected=diff.left_value,
                        actual=diff.right_value,
                        severity=severity,
                    )
                )
        return items

    # -- Sync recommendations -------------------------------------------------

    @staticmethod
    def _generate_recommendations(result: ComparisonResult) -> list[SyncRecommendation]:
        recs: list[SyncRecommendation] = []
        for diff in result.config_diffs:
            if diff.kind == DiffKind.CHANGED:
                recs.append(
                    SyncRecommendation(
                        action="update",
                        key=diff.key,
                        value=diff.left_value,
                        reason=f"Sync {diff.key} from {result.left_name} to {result.right_name}",
                    )
                )
            elif diff.kind == DiffKind.REMOVED:
                recs.append(
                    SyncRecommendation(
                        action="remove",
                        key=diff.key,
                        value=diff.left_value,
                        reason=f"Key {diff.key} exists only in {result.left_name}",
                    )
                )
            elif diff.kind == DiffKind.ADDED:
                recs.append(
                    SyncRecommendation(
                        action="add",
                        key=diff.key,
                        value=diff.right_value,
                        reason=f"Key {diff.key} exists only in {result.right_name}",
                    )
                )
        return recs
