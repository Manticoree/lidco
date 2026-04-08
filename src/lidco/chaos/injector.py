"""
Fault Injector — inject faults like timeouts, error responses, slow responses,
connection drops. Supports safe rollback of injected faults.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class FaultType(Enum):
    """Types of injectable faults."""

    TIMEOUT = "timeout"
    ERROR_RESPONSE = "error_response"
    SLOW_RESPONSE = "slow_response"
    CONNECTION_DROP = "connection_drop"
    EXCEPTION = "exception"
    CUSTOM = "custom"


class FaultStatus(Enum):
    """Status of an injected fault."""

    ACTIVE = "active"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"


@dataclass(frozen=True)
class FaultConfig:
    """Configuration for a fault to inject."""

    fault_type: FaultType
    target: str
    duration_seconds: float = 10.0
    probability: float = 1.0
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("probability must be between 0.0 and 1.0")
        if not self.target:
            raise ValueError("target must not be empty")


@dataclass
class InjectedFault:
    """An active injected fault."""

    id: str
    config: FaultConfig
    status: FaultStatus = FaultStatus.ACTIVE
    injected_at: float = 0.0
    rolled_back_at: float = 0.0
    invocation_count: int = 0

    @property
    def is_expired(self) -> bool:
        if self.status != FaultStatus.ACTIVE:
            return False
        return (time.time() - self.injected_at) > self.config.duration_seconds


class FaultInjector:
    """Inject and manage faults in the system."""

    def __init__(self) -> None:
        self._faults: dict[str, InjectedFault] = {}
        self._interceptors: dict[str, Callable[..., Any]] = {}
        self._rollback_log: list[dict[str, Any]] = []

    def inject(self, config: FaultConfig) -> InjectedFault:
        """Inject a fault with the given configuration."""
        fault = InjectedFault(
            id=uuid.uuid4().hex[:12],
            config=config,
            status=FaultStatus.ACTIVE,
            injected_at=time.time(),
        )
        self._faults = {**self._faults, fault.id: fault}
        return fault

    def rollback(self, fault_id: str) -> InjectedFault:
        """Roll back an injected fault, making it inactive."""
        fault = self._faults.get(fault_id)
        if fault is None:
            raise KeyError(f"Fault {fault_id!r} not found")
        if fault.status != FaultStatus.ACTIVE:
            raise RuntimeError(
                f"Cannot rollback fault in {fault.status.value} state"
            )
        updated = InjectedFault(
            id=fault.id,
            config=fault.config,
            status=FaultStatus.ROLLED_BACK,
            injected_at=fault.injected_at,
            rolled_back_at=time.time(),
            invocation_count=fault.invocation_count,
        )
        self._faults = {**self._faults, fault.id: updated}
        self._rollback_log = [
            *self._rollback_log,
            {
                "fault_id": fault.id,
                "fault_type": fault.config.fault_type.value,
                "target": fault.config.target,
                "rolled_back_at": updated.rolled_back_at,
            },
        ]
        return updated

    def rollback_all(self) -> list[InjectedFault]:
        """Roll back all active faults."""
        rolled = []
        for fid, fault in self._faults.items():
            if fault.status == FaultStatus.ACTIVE:
                rolled.append(self.rollback(fid))
        return rolled

    def get_fault(self, fault_id: str) -> InjectedFault | None:
        return self._faults.get(fault_id)

    def list_active(self) -> list[InjectedFault]:
        """List all currently active (non-expired) faults."""
        result = []
        for fault in self._faults.values():
            if fault.status == FaultStatus.ACTIVE and not fault.is_expired:
                result.append(fault)
        return result

    def list_all(self) -> list[InjectedFault]:
        return list(self._faults.values())

    def check_fault(self, target: str) -> FaultType | None:
        """Check if a target has an active fault. Returns fault type or None."""
        for fault in self._faults.values():
            if (
                fault.status == FaultStatus.ACTIVE
                and not fault.is_expired
                and fault.config.target == target
            ):
                # Update invocation count immutably
                updated = InjectedFault(
                    id=fault.id,
                    config=fault.config,
                    status=fault.status,
                    injected_at=fault.injected_at,
                    rolled_back_at=fault.rolled_back_at,
                    invocation_count=fault.invocation_count + 1,
                )
                self._faults = {**self._faults, fault.id: updated}
                return fault.config.fault_type
        return None

    def expire_stale(self) -> list[InjectedFault]:
        """Expire all faults past their duration."""
        expired = []
        for fault in self._faults.values():
            if fault.status == FaultStatus.ACTIVE and fault.is_expired:
                updated = InjectedFault(
                    id=fault.id,
                    config=fault.config,
                    status=FaultStatus.EXPIRED,
                    injected_at=fault.injected_at,
                    invocation_count=fault.invocation_count,
                )
                self._faults = {**self._faults, fault.id: updated}
                expired.append(updated)
        return expired

    @property
    def rollback_log(self) -> list[dict[str, Any]]:
        return list(self._rollback_log)
