"""Tenant router — route requests to correct tenant context; session affinity."""
from __future__ import annotations

from dataclasses import dataclass

from lidco.tenant.manager import TenantManager


@dataclass(frozen=True)
class RouteResult:
    """Result of routing a request to a tenant."""

    tenant_id: str
    session_id: str | None
    matched_by: str  # "session" | "header" | "default"


class TenantRouter:
    """Route requests to the correct tenant context with session affinity."""

    def __init__(
        self,
        manager: TenantManager,
        default_tenant: str | None = None,
    ) -> None:
        self._manager = manager
        self._default_tenant = default_tenant
        self._sessions: dict[str, str] = {}  # session_id -> tenant_id

    def bind_session(self, session_id: str, tenant_id: str) -> None:
        """Bind a session to a tenant."""
        if self._manager.get(tenant_id) is None:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        self._sessions[session_id] = tenant_id

    def unbind_session(self, session_id: str) -> bool:
        """Remove a session binding. Returns True if existed."""
        return self._sessions.pop(session_id, None) is not None

    def route(
        self,
        session_id: str | None = None,
        tenant_header: str | None = None,
    ) -> RouteResult:
        """Route a request to a tenant.

        Priority: session binding > tenant header > default tenant.
        """
        # 1. Session affinity
        if session_id and session_id in self._sessions:
            tid = self._sessions[session_id]
            return RouteResult(tenant_id=tid, session_id=session_id, matched_by="session")

        # 2. Explicit header
        if tenant_header and self._manager.get(tenant_header) is not None:
            return RouteResult(tenant_id=tenant_header, session_id=session_id, matched_by="header")

        # 3. Default
        if self._default_tenant and self._manager.get(self._default_tenant) is not None:
            return RouteResult(
                tenant_id=self._default_tenant,
                session_id=session_id,
                matched_by="default",
            )

        raise ValueError("No tenant could be resolved")

    def sessions_for_tenant(self, tenant_id: str) -> list[str]:
        """Return all session ids bound to *tenant_id*."""
        return [sid for sid, tid in self._sessions.items() if tid == tenant_id]

    def active_bindings(self) -> dict[str, str]:
        """Return a copy of session -> tenant bindings."""
        return dict(self._sessions)

    def summary(self) -> dict:
        """Return a summary dict."""
        return {
            "bindings": len(self._sessions),
            "default_tenant": self._default_tenant,
        }
