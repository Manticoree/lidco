"""Env Promoter — promote changes between environments.

Approval gates, smoke tests, rollback support.
"""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from lidco.envmgmt.provisioner import EnvStatus, EnvTier, Environment


class PromotionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROMOTING = "promoting"
    SMOKE_TESTING = "smoke_testing"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class PromotionRecord:
    """Tracks a single promotion attempt."""

    promotion_id: str
    source_env_id: str
    target_env_id: str
    status: PromotionStatus
    changes: dict[str, Any]
    previous_config: dict[str, Any]
    approved_by: str | None = None
    created_at: float = 0.0
    completed_at: float | None = None
    error: str | None = None


# Type alias for smoke-test callables
SmokeTest = Callable[[Environment], bool]


class PromotionError(Exception):
    """Raised when a promotion fails."""


class EnvPromoter:
    """Promote configuration changes between environments."""

    # Allowed promotion paths: source tier -> allowed target tiers
    PROMOTION_PATHS: dict[EnvTier, list[EnvTier]] = {
        EnvTier.DEV: [EnvTier.STAGING],
        EnvTier.STAGING: [EnvTier.PROD],
    }

    def __init__(self) -> None:
        self._records: dict[str, PromotionRecord] = {}
        self._smoke_tests: list[SmokeTest] = []
        self._require_approval: bool = True

    # -- Smoke tests ----------------------------------------------------------

    def register_smoke_test(self, test: SmokeTest) -> None:
        self._smoke_tests.append(test)

    # -- Settings -------------------------------------------------------------

    def set_require_approval(self, value: bool) -> None:
        self._require_approval = value

    # -- Create promotion request ---------------------------------------------

    def create_promotion(
        self,
        source: Environment,
        target: Environment,
        *,
        changes: dict[str, Any] | None = None,
    ) -> PromotionRecord:
        """Create a promotion request from source to target."""
        allowed = self.PROMOTION_PATHS.get(source.tier, [])
        if target.tier not in allowed:
            raise PromotionError(
                f"Cannot promote from {source.tier.value} to {target.tier.value}"
            )

        if source.status != EnvStatus.ACTIVE:
            raise PromotionError("Source environment is not active")
        if target.status != EnvStatus.ACTIVE:
            raise PromotionError("Target environment is not active")

        effective_changes = changes if changes is not None else dict(source.config)

        record = PromotionRecord(
            promotion_id=uuid.uuid4().hex,
            source_env_id=source.env_id,
            target_env_id=target.env_id,
            status=PromotionStatus.PENDING if self._require_approval else PromotionStatus.APPROVED,
            changes=effective_changes,
            previous_config=copy.deepcopy(target.config),
            created_at=time.time(),
        )
        self._records[record.promotion_id] = record
        return record

    # -- Approval gate --------------------------------------------------------

    def approve(self, promotion_id: str, approver: str) -> PromotionRecord:
        record = self._get_record(promotion_id)
        if record.status != PromotionStatus.PENDING:
            raise PromotionError(f"Promotion not pending: {record.status.value}")
        record.status = PromotionStatus.APPROVED
        record.approved_by = approver
        return record

    def reject(self, promotion_id: str, reason: str = "") -> PromotionRecord:
        record = self._get_record(promotion_id)
        if record.status != PromotionStatus.PENDING:
            raise PromotionError(f"Promotion not pending: {record.status.value}")
        record.status = PromotionStatus.REJECTED
        record.error = reason or "Rejected"
        return record

    # -- Execute promotion ----------------------------------------------------

    def execute(
        self, promotion_id: str, target: Environment
    ) -> PromotionRecord:
        """Apply promotion changes to target environment."""
        record = self._get_record(promotion_id)
        if record.status != PromotionStatus.APPROVED:
            raise PromotionError(
                f"Promotion not approved: {record.status.value}"
            )

        record.status = PromotionStatus.PROMOTING
        record.previous_config = copy.deepcopy(target.config)

        # Apply changes
        target.config.update(record.changes)
        target.updated_at = time.time()

        # Run smoke tests
        if self._smoke_tests:
            record.status = PromotionStatus.SMOKE_TESTING
            for test in self._smoke_tests:
                try:
                    if not test(target):
                        # Rollback
                        target.config = copy.deepcopy(record.previous_config)
                        target.updated_at = time.time()
                        record.status = PromotionStatus.FAILED
                        record.error = "Smoke test failed"
                        return record
                except Exception as exc:
                    target.config = copy.deepcopy(record.previous_config)
                    target.updated_at = time.time()
                    record.status = PromotionStatus.FAILED
                    record.error = f"Smoke test error: {exc}"
                    return record

        record.status = PromotionStatus.COMPLETED
        record.completed_at = time.time()
        return record

    # -- Rollback -------------------------------------------------------------

    def rollback(
        self, promotion_id: str, target: Environment
    ) -> PromotionRecord:
        """Rollback a completed promotion."""
        record = self._get_record(promotion_id)
        if record.status != PromotionStatus.COMPLETED:
            raise PromotionError("Can only rollback completed promotions")

        target.config = copy.deepcopy(record.previous_config)
        target.updated_at = time.time()
        record.status = PromotionStatus.ROLLED_BACK
        return record

    # -- Query ----------------------------------------------------------------

    def get_record(self, promotion_id: str) -> PromotionRecord | None:
        return self._records.get(promotion_id)

    def list_records(
        self, *, status: PromotionStatus | None = None
    ) -> list[PromotionRecord]:
        result: list[PromotionRecord] = []
        for rec in self._records.values():
            if status is not None and rec.status != status:
                continue
            result.append(rec)
        return result

    # -- Internal -------------------------------------------------------------

    def _get_record(self, promotion_id: str) -> PromotionRecord:
        record = self._records.get(promotion_id)
        if record is None:
            raise PromotionError(f"Promotion not found: {promotion_id}")
        return record
