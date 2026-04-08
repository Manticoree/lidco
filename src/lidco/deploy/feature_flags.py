"""FeatureFlagDeployer — feature flag-based deployment with gradual rollout,
user targeting, kill switch, and experimentation support (stdlib only)."""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FlagState(str, Enum):
    """State of a feature flag."""

    DISABLED = "disabled"
    GRADUAL = "gradual"
    TARGETED = "targeted"
    ENABLED = "enabled"
    KILLED = "killed"


class RolloutPhase(str, Enum):
    """Rollout lifecycle."""

    CREATED = "created"
    ROLLING_OUT = "rolling_out"
    STABLE = "stable"
    KILLED = "killed"


@dataclass
class FeatureFlag:
    """A single feature flag with rollout configuration."""

    flag_id: str = ""
    name: str = ""
    description: str = ""
    state: FlagState = FlagState.DISABLED
    rollout_pct: float = 0.0
    target_users: list[str] = field(default_factory=list)
    target_groups: list[str] = field(default_factory=list)
    exclude_users: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.flag_id:
            self.flag_id = uuid.uuid4().hex
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now


@dataclass
class RolloutPlan:
    """A gradual rollout plan for a feature flag."""

    plan_id: str = ""
    flag_id: str = ""
    steps: list[float] = field(default_factory=lambda: [5.0, 25.0, 50.0, 100.0])
    current_step: int = 0
    phase: RolloutPhase = RolloutPhase.CREATED
    started_at: float = 0.0
    finished_at: float = 0.0
    logs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.plan_id:
            self.plan_id = uuid.uuid4().hex

    @property
    def progress_pct(self) -> float:
        if not self.steps:
            return 0.0
        if self.current_step >= len(self.steps):
            return 100.0
        return self.steps[self.current_step - 1] if self.current_step > 0 else 0.0


@dataclass
class ExperimentResult:
    """Result of an A/B experiment associated with a flag."""

    flag_id: str = ""
    control_count: int = 0
    treatment_count: int = 0
    control_success: int = 0
    treatment_success: int = 0

    @property
    def control_rate(self) -> float:
        return self.control_success / self.control_count if self.control_count else 0.0

    @property
    def treatment_rate(self) -> float:
        return self.treatment_success / self.treatment_count if self.treatment_count else 0.0

    @property
    def lift(self) -> float:
        if self.control_rate == 0:
            return 0.0
        return (self.treatment_rate - self.control_rate) / self.control_rate


class FeatureFlagDeployer:
    """Manages feature-flag-based deployments with gradual rollout and targeting."""

    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}
        self._plans: dict[str, RolloutPlan] = {}
        self._experiments: dict[str, ExperimentResult] = {}
        self._user_groups: dict[str, list[str]] = {}

    # -- flag CRUD ----------------------------------------------------------

    def create_flag(
        self,
        name: str,
        description: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> FeatureFlag:
        """Create a new feature flag (disabled by default)."""
        flag = FeatureFlag(name=name, description=description, metadata=metadata or {})
        self._flags[flag.flag_id] = flag
        return flag

    def get_flag(self, flag_id: str) -> Optional[FeatureFlag]:
        return self._flags.get(flag_id)

    def list_flags(self) -> list[FeatureFlag]:
        return list(self._flags.values())

    def delete_flag(self, flag_id: str) -> bool:
        if flag_id in self._flags:
            del self._flags[flag_id]
            self._plans.pop(flag_id, None)
            self._experiments.pop(flag_id, None)
            return True
        return False

    # -- evaluation ---------------------------------------------------------

    def is_enabled(self, flag_id: str, user_id: Optional[str] = None, groups: Optional[list[str]] = None) -> bool:
        """Check if a flag is enabled for the given user/groups."""
        flag = self._flags.get(flag_id)
        if flag is None:
            return False
        if flag.state == FlagState.KILLED or flag.state == FlagState.DISABLED:
            return False
        if flag.state == FlagState.ENABLED:
            return user_id not in flag.exclude_users if user_id else True

        # check exclusion
        if user_id and user_id in flag.exclude_users:
            return False

        # targeted
        if flag.state == FlagState.TARGETED:
            if user_id and user_id in flag.target_users:
                return True
            if groups:
                for g in groups:
                    if g in flag.target_groups:
                        return True
            return False

        # gradual — hash-based sticky assignment
        if flag.state == FlagState.GRADUAL and user_id:
            bucket = self._hash_bucket(flag_id, user_id)
            return bucket < flag.rollout_pct

        return False

    # -- rollout ------------------------------------------------------------

    def start_rollout(self, flag_id: str, steps: Optional[list[float]] = None) -> Optional[RolloutPlan]:
        """Begin a gradual rollout for the given flag."""
        flag = self._flags.get(flag_id)
        if flag is None:
            return None

        plan = RolloutPlan(
            flag_id=flag_id,
            steps=steps or [5.0, 25.0, 50.0, 100.0],
            phase=RolloutPhase.ROLLING_OUT,
            started_at=time.time(),
        )
        self._plans[flag_id] = plan

        # advance to first step
        return self.advance_rollout(flag_id)

    def advance_rollout(self, flag_id: str) -> Optional[RolloutPlan]:
        """Advance rollout to the next percentage step."""
        plan = self._plans.get(flag_id)
        flag = self._flags.get(flag_id)
        if plan is None or flag is None:
            return None
        if plan.phase == RolloutPhase.KILLED:
            return plan

        if plan.current_step >= len(plan.steps):
            plan.phase = RolloutPhase.STABLE
            plan.finished_at = time.time()
            plan.logs.append("Rollout complete — 100%")
            flag.state = FlagState.ENABLED
            flag.rollout_pct = 100.0
            flag.updated_at = time.time()
            return plan

        pct = plan.steps[plan.current_step]
        flag.state = FlagState.GRADUAL
        flag.rollout_pct = pct
        flag.updated_at = time.time()
        plan.current_step += 1
        plan.logs.append(f"Advanced to {pct}% (step {plan.current_step}/{len(plan.steps)})")
        plan.phase = RolloutPhase.ROLLING_OUT

        if plan.current_step >= len(plan.steps) and pct >= 100.0:
            plan.phase = RolloutPhase.STABLE
            plan.finished_at = time.time()
            flag.state = FlagState.ENABLED

        return plan

    # -- targeting ----------------------------------------------------------

    def set_targets(
        self,
        flag_id: str,
        users: Optional[list[str]] = None,
        groups: Optional[list[str]] = None,
        exclude: Optional[list[str]] = None,
    ) -> Optional[FeatureFlag]:
        """Set user/group targeting for a flag."""
        flag = self._flags.get(flag_id)
        if flag is None:
            return None
        updated = FeatureFlag(
            flag_id=flag.flag_id,
            name=flag.name,
            description=flag.description,
            state=FlagState.TARGETED if (users or groups) else flag.state,
            rollout_pct=flag.rollout_pct,
            target_users=users if users is not None else flag.target_users,
            target_groups=groups if groups is not None else flag.target_groups,
            exclude_users=exclude if exclude is not None else flag.exclude_users,
            metadata=flag.metadata,
            created_at=flag.created_at,
            updated_at=time.time(),
        )
        self._flags[flag_id] = updated
        return updated

    # -- kill switch --------------------------------------------------------

    def kill(self, flag_id: str) -> bool:
        """Emergency kill switch — immediately disable a flag."""
        flag = self._flags.get(flag_id)
        if flag is None:
            return False
        flag.state = FlagState.KILLED
        flag.updated_at = time.time()
        plan = self._plans.get(flag_id)
        if plan:
            plan.phase = RolloutPhase.KILLED
            plan.finished_at = time.time()
            plan.logs.append("KILLED — flag disabled immediately")
        return True

    def enable(self, flag_id: str) -> bool:
        """Fully enable a flag for all users."""
        flag = self._flags.get(flag_id)
        if flag is None:
            return False
        flag.state = FlagState.ENABLED
        flag.rollout_pct = 100.0
        flag.updated_at = time.time()
        return True

    # -- experimentation ----------------------------------------------------

    def register_group(self, group_name: str, user_ids: list[str]) -> None:
        """Register a named user group for targeting."""
        self._user_groups[group_name] = list(user_ids)

    def record_experiment(
        self,
        flag_id: str,
        user_id: str,
        success: bool,
    ) -> Optional[ExperimentResult]:
        """Record an experiment data point."""
        if flag_id not in self._flags:
            return None
        exp = self._experiments.setdefault(
            flag_id, ExperimentResult(flag_id=flag_id)
        )
        in_treatment = self.is_enabled(flag_id, user_id=user_id)
        if in_treatment:
            exp.treatment_count += 1
            if success:
                exp.treatment_success += 1
        else:
            exp.control_count += 1
            if success:
                exp.control_success += 1
        return exp

    def get_experiment(self, flag_id: str) -> Optional[ExperimentResult]:
        return self._experiments.get(flag_id)

    # -- status -------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        return {
            "total_flags": len(self._flags),
            "enabled": sum(1 for f in self._flags.values() if f.state == FlagState.ENABLED),
            "gradual": sum(1 for f in self._flags.values() if f.state == FlagState.GRADUAL),
            "killed": sum(1 for f in self._flags.values() if f.state == FlagState.KILLED),
            "active_rollouts": sum(
                1 for p in self._plans.values() if p.phase == RolloutPhase.ROLLING_OUT
            ),
        }

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _hash_bucket(flag_id: str, user_id: str) -> float:
        h = hashlib.md5(f"{flag_id}:{user_id}".encode()).hexdigest()  # noqa: S324
        return (int(h[:8], 16) / 0xFFFFFFFF) * 100.0
