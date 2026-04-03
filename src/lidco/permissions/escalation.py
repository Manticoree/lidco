"""Permission escalation — request elevated permissions with time-limited grants."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EscalationRequest:
    """A request to escalate permissions."""

    id: str
    scope: str
    resource: str
    reason: str
    requested_at: float
    ttl: float = 300.0
    status: str = "pending"


@dataclass(frozen=True)
class EscalationGrant:
    """An approved escalation grant."""

    request_id: str
    granted_at: float
    expires_at: float
    scope: str
    resource: str


class EscalationManager:
    """Manage permission escalation requests and grants."""

    def __init__(self, default_ttl: float = 300.0) -> None:
        self._default_ttl = default_ttl
        self._requests: dict[str, EscalationRequest] = {}
        self._grants: dict[str, EscalationGrant] = {}

    def request(
        self,
        scope: str,
        resource: str,
        reason: str,
        ttl: float | None = None,
    ) -> EscalationRequest:
        """Create an escalation request."""
        req = EscalationRequest(
            id=uuid.uuid4().hex[:12],
            scope=scope,
            resource=resource,
            reason=reason,
            requested_at=time.time(),
            ttl=ttl if ttl is not None else self._default_ttl,
        )
        self._requests[req.id] = req
        return req

    def approve(self, request_id: str) -> EscalationGrant:
        """Approve a pending request and create a grant."""
        req = self._requests.get(request_id)
        if req is None:
            raise KeyError(f"Request {request_id} not found")
        if req.status != "pending":
            raise ValueError(f"Request {request_id} is {req.status}, not pending")
        now = time.time()
        grant = EscalationGrant(
            request_id=request_id,
            granted_at=now,
            expires_at=now + req.ttl,
            scope=req.scope,
            resource=req.resource,
        )
        # Mark request approved (frozen, so replace)
        self._requests[request_id] = EscalationRequest(
            id=req.id,
            scope=req.scope,
            resource=req.resource,
            reason=req.reason,
            requested_at=req.requested_at,
            ttl=req.ttl,
            status="approved",
        )
        self._grants[request_id] = grant
        return grant

    def deny(self, request_id: str) -> EscalationRequest:
        """Deny a pending request."""
        req = self._requests.get(request_id)
        if req is None:
            raise KeyError(f"Request {request_id} not found")
        if req.status != "pending":
            raise ValueError(f"Request {request_id} is {req.status}, not pending")
        denied = EscalationRequest(
            id=req.id,
            scope=req.scope,
            resource=req.resource,
            reason=req.reason,
            requested_at=req.requested_at,
            ttl=req.ttl,
            status="denied",
        )
        self._requests[request_id] = denied
        return denied

    def check(self, scope: str, resource: str) -> bool:
        """Return True if an active non-expired grant covers *scope*/*resource*."""
        now = time.time()
        for grant in self._grants.values():
            if (
                grant.scope == scope
                and grant.resource == resource
                and grant.expires_at > now
            ):
                return True
        return False

    def revoke(self, request_id: str) -> bool:
        """Revoke an active grant. Returns True if removed."""
        if request_id in self._grants:
            del self._grants[request_id]
            return True
        return False

    def active_grants(self) -> list[EscalationGrant]:
        """Return all non-expired grants."""
        now = time.time()
        return [g for g in self._grants.values() if g.expires_at > now]

    def cleanup_expired(self) -> int:
        """Remove expired grants and return the count removed."""
        now = time.time()
        expired = [
            rid for rid, g in self._grants.items() if g.expires_at <= now
        ]
        for rid in expired:
            del self._grants[rid]
            # Also mark the request as expired
            req = self._requests.get(rid)
            if req is not None and req.status == "approved":
                self._requests[rid] = EscalationRequest(
                    id=req.id,
                    scope=req.scope,
                    resource=req.resource,
                    reason=req.reason,
                    requested_at=req.requested_at,
                    ttl=req.ttl,
                    status="expired",
                )
        return len(expired)
