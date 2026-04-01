"""
Approval Gate — workflow checkpoints with timeout, default action,
and audit log.

Stdlib only — no external dependencies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ApprovalError(Exception):
    """Raised on approval gate errors."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApprovalGate:
    """A named approval checkpoint in a workflow."""

    name: str
    description: str = ""
    timeout_seconds: float = 300.0
    default_action: str = "approve"  # "approve" or "reject"
    require_reason: bool = False


@dataclass
class ApprovalRequest:
    """A pending/resolved approval request."""

    gate_name: str
    requester: str
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # "pending", "approved", "rejected"
    reason: str = ""
    requested_at: float = 0.0
    resolved_at: float = 0.0


# ---------------------------------------------------------------------------
# Approval Manager
# ---------------------------------------------------------------------------

class ApprovalManager:
    """Manage approval gates, requests, and audit log."""

    def __init__(self) -> None:
        self._gates: dict[str, ApprovalGate] = {}
        self._requests: dict[str, ApprovalRequest] = {}
        self._next_id: int = 1

    # ------------------------------------------------------------------
    # Gate management
    # ------------------------------------------------------------------

    def add_gate(self, gate: ApprovalGate) -> None:
        """Register an approval gate."""
        self._gates[gate.name] = gate

    def remove_gate(self, name: str) -> bool:
        """Remove a gate by name. Returns True if found."""
        return self._gates.pop(name, None) is not None

    def get_gate(self, name: str) -> ApprovalGate | None:
        """Get a gate by name."""
        return self._gates.get(name)

    def list_gates(self) -> list[ApprovalGate]:
        """List all registered gates."""
        return list(self._gates.values())

    # ------------------------------------------------------------------
    # Request management
    # ------------------------------------------------------------------

    def request_approval(
        self,
        gate_name: str,
        requester: str,
        context: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Create a pending approval request.

        Raises ApprovalError if the gate does not exist.
        """
        gate = self._gates.get(gate_name)
        if gate is None:
            raise ApprovalError(f"Gate '{gate_name}' not found")

        request_id = str(self._next_id)
        self._next_id += 1

        request = ApprovalRequest(
            gate_name=gate_name,
            requester=requester,
            context=dict(context or {}),
            status="pending",
            requested_at=time.time(),
        )
        self._requests[request_id] = request
        return request

    def approve(self, request_id: str, reason: str = "") -> ApprovalRequest:
        """Approve a pending request.

        Raises ApprovalError if request not found or not pending.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise ApprovalError(f"Request '{request_id}' not found")
        if request.status != "pending":
            raise ApprovalError(
                f"Request '{request_id}' is already {request.status}"
            )

        gate = self._gates.get(request.gate_name)
        if gate and gate.require_reason and not reason:
            raise ApprovalError("Reason is required for this gate")

        request.status = "approved"
        request.reason = reason
        request.resolved_at = time.time()
        return request

    def reject(self, request_id: str, reason: str = "") -> ApprovalRequest:
        """Reject a pending request.

        Raises ApprovalError if request not found or not pending.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise ApprovalError(f"Request '{request_id}' not found")
        if request.status != "pending":
            raise ApprovalError(
                f"Request '{request_id}' is already {request.status}"
            )

        gate = self._gates.get(request.gate_name)
        if gate and gate.require_reason and not reason:
            raise ApprovalError("Reason is required for this gate")

        request.status = "rejected"
        request.reason = reason
        request.resolved_at = time.time()
        return request

    def check_timeouts(self) -> list[ApprovalRequest]:
        """Auto-resolve expired pending requests using gate's default_action.

        Returns list of requests that were auto-resolved.
        """
        now = time.time()
        resolved: list[ApprovalRequest] = []

        for request in self._requests.values():
            if request.status != "pending":
                continue
            gate = self._gates.get(request.gate_name)
            if gate is None:
                continue
            elapsed = now - request.requested_at
            if elapsed >= gate.timeout_seconds:
                request.status = gate.default_action + "d" if gate.default_action == "approve" else gate.default_action + "ed"
                # Normalize: "approve" -> "approved", "reject" -> "rejected"
                if gate.default_action == "approve":
                    request.status = "approved"
                else:
                    request.status = "rejected"
                request.reason = "auto: timeout"
                request.resolved_at = now
                resolved.append(request)

        return resolved

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """Get a request by ID."""
        return self._requests.get(request_id)

    def list_requests(
        self,
        gate_name: str | None = None,
        status: str | None = None,
    ) -> list[ApprovalRequest]:
        """List requests, optionally filtered by gate_name and/or status."""
        results: list[ApprovalRequest] = []
        for req in self._requests.values():
            if gate_name is not None and req.gate_name != gate_name:
                continue
            if status is not None and req.status != status:
                continue
            results.append(req)
        return results

    def audit_log(self) -> list[dict[str, Any]]:
        """Return all resolved requests as dicts for auditing."""
        log: list[dict[str, Any]] = []
        for req_id, req in self._requests.items():
            if req.status == "pending":
                continue
            log.append({
                "id": req_id,
                "gate_name": req.gate_name,
                "requester": req.requester,
                "status": req.status,
                "reason": req.reason,
                "requested_at": req.requested_at,
                "resolved_at": req.resolved_at,
                "context": req.context,
            })
        return log
