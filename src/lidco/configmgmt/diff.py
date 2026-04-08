"""Config Diff — diff configs between environments.

Highlight dangerous changes, approval workflow support.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChangeKind(Enum):
    """Type of config change."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class RiskLevel(Enum):
    """Risk level of a config change."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ConfigChange:
    """A single config key change between two configs."""

    path: str
    kind: ChangeKind
    old_value: Any = None
    new_value: Any = None
    risk: RiskLevel = RiskLevel.LOW


@dataclass(frozen=True)
class DiffResult:
    """Result of diffing two configs."""

    changes: list[ConfigChange] = field(default_factory=list)
    source_name: str = ""
    target_name: str = ""

    @property
    def total_changes(self) -> int:
        return len(self.changes)

    @property
    def added(self) -> list[ConfigChange]:
        return [c for c in self.changes if c.kind is ChangeKind.ADDED]

    @property
    def removed(self) -> list[ConfigChange]:
        return [c for c in self.changes if c.kind is ChangeKind.REMOVED]

    @property
    def modified(self) -> list[ConfigChange]:
        return [c for c in self.changes if c.kind is ChangeKind.MODIFIED]

    @property
    def dangerous_changes(self) -> list[ConfigChange]:
        return [c for c in self.changes if c.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)]

    @property
    def needs_approval(self) -> bool:
        return len(self.dangerous_changes) > 0


@dataclass(frozen=True)
class ApprovalRequest:
    """A request for approval of config changes."""

    diff: DiffResult
    requester: str = ""
    reason: str = ""
    approved: bool = False
    approver: str = ""


class ConfigDiff:
    """Diff configuration dictionaries and highlight risks."""

    def __init__(self) -> None:
        self._dangerous_keys: set[str] = set()
        self._critical_keys: set[str] = set()
        self._approvals: list[ApprovalRequest] = []

    # -- Risk configuration ------------------------------------------------

    def mark_dangerous(self, *keys: str) -> None:
        """Mark key patterns as HIGH risk when changed."""
        self._dangerous_keys.update(keys)

    def mark_critical(self, *keys: str) -> None:
        """Mark key patterns as CRITICAL risk when changed."""
        self._critical_keys.update(keys)

    # -- Diffing -----------------------------------------------------------

    def diff(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
        *,
        source_name: str = "source",
        target_name: str = "target",
    ) -> DiffResult:
        """Compute diff between two config dicts."""
        changes: list[ConfigChange] = []
        self._diff_recursive(source, target, "", changes)
        return DiffResult(
            changes=changes,
            source_name=source_name,
            target_name=target_name,
        )

    def diff_environments(
        self,
        configs: dict[str, dict[str, Any]],
        base: str,
        target: str,
    ) -> DiffResult:
        """Diff two named environment configs."""
        if base not in configs:
            raise KeyError(f"Environment not found: {base}")
        if target not in configs:
            raise KeyError(f"Environment not found: {target}")
        return self.diff(
            configs[base], configs[target],
            source_name=base, target_name=target,
        )

    # -- Approval workflow -------------------------------------------------

    def request_approval(self, diff: DiffResult, requester: str = "", reason: str = "") -> ApprovalRequest:
        """Create an approval request for a diff."""
        req = ApprovalRequest(diff=diff, requester=requester, reason=reason)
        self._approvals.append(req)
        return req

    def approve(self, request: ApprovalRequest, approver: str) -> ApprovalRequest:
        """Approve a request, returning a new approved copy."""
        approved = ApprovalRequest(
            diff=request.diff,
            requester=request.requester,
            reason=request.reason,
            approved=True,
            approver=approver,
        )
        # Replace in list
        self._approvals = [
            approved if r is request else r for r in self._approvals
        ]
        return approved

    def pending_approvals(self) -> list[ApprovalRequest]:
        """Return all unapproved requests."""
        return [r for r in self._approvals if not r.approved]

    # -- Summary -----------------------------------------------------------

    def summary(self, result: DiffResult) -> str:
        """Human-readable summary."""
        lines = [
            f"Config diff: {result.source_name} -> {result.target_name}",
            f"  Added: {len(result.added)}",
            f"  Removed: {len(result.removed)}",
            f"  Modified: {len(result.modified)}",
        ]
        dangerous = result.dangerous_changes
        if dangerous:
            lines.append(f"  Dangerous: {len(dangerous)}")
            for c in dangerous:
                lines.append(f"    [{c.risk.value}] {c.path}: {c.old_value!r} -> {c.new_value!r}")
        return "\n".join(lines)

    # -- Internals ---------------------------------------------------------

    def _diff_recursive(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
        prefix: str,
        changes: list[ConfigChange],
    ) -> None:
        all_keys = set(source) | set(target)
        for key in sorted(all_keys):
            path = f"{prefix}.{key}" if prefix else key
            in_src = key in source
            in_tgt = key in target

            if in_src and not in_tgt:
                changes.append(ConfigChange(
                    path=path,
                    kind=ChangeKind.REMOVED,
                    old_value=source[key],
                    risk=self._assess_risk(path),
                ))
            elif not in_src and in_tgt:
                changes.append(ConfigChange(
                    path=path,
                    kind=ChangeKind.ADDED,
                    new_value=target[key],
                    risk=self._assess_risk(path),
                ))
            elif source[key] != target[key]:
                # Both present but different
                if isinstance(source[key], dict) and isinstance(target[key], dict):
                    self._diff_recursive(source[key], target[key], path, changes)
                else:
                    changes.append(ConfigChange(
                        path=path,
                        kind=ChangeKind.MODIFIED,
                        old_value=source[key],
                        new_value=target[key],
                        risk=self._assess_risk(path),
                    ))

    def _assess_risk(self, path: str) -> RiskLevel:
        for pattern in self._critical_keys:
            if pattern in path:
                return RiskLevel.CRITICAL
        for pattern in self._dangerous_keys:
            if pattern in path:
                return RiskLevel.HIGH
        return RiskLevel.LOW
