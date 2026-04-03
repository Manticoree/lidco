"""Tenant manager — create/delete tenants, resource quotas, config inheritance."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Tenant:
    """A single tenant."""

    id: str
    name: str
    created_at: float
    active: bool = True
    config: dict = field(default_factory=dict)
    parent_id: str | None = None


class TenantManager:
    """Create/delete tenants; resource quotas; isolation; config inheritance."""

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}

    def create(
        self,
        name: str,
        config: dict | None = None,
        parent_id: str | None = None,
    ) -> Tenant:
        """Create a new tenant."""
        if parent_id is not None and parent_id not in self._tenants:
            raise ValueError(f"Parent tenant '{parent_id}' not found")
        tenant = Tenant(
            id=uuid.uuid4().hex[:12],
            name=name,
            created_at=time.time(),
            config=dict(config) if config else {},
            parent_id=parent_id,
        )
        self._tenants[tenant.id] = tenant
        return tenant

    def get(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by id."""
        return self._tenants.get(tenant_id)

    def delete(self, tenant_id: str) -> bool:
        """Soft-delete a tenant (set active=False)."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return False
        tenant.active = False
        return True

    def activate(self, tenant_id: str) -> bool:
        """Re-activate a soft-deleted tenant."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return False
        tenant.active = True
        return True

    def update_config(self, tenant_id: str, config: dict) -> Tenant | None:
        """Merge *config* into the tenant's existing config."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return None
        merged = {**tenant.config, **config}
        tenant.config = merged
        return tenant

    def resolve_config(self, tenant_id: str) -> dict:
        """Resolve config by walking the parent chain (parent first, child overrides)."""
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            return {}
        chain: list[Tenant] = []
        current: Tenant | None = tenant
        seen: set[str] = set()
        while current is not None and current.id not in seen:
            chain.append(current)
            seen.add(current.id)
            current = self._tenants.get(current.parent_id) if current.parent_id else None
        resolved: dict = {}
        for t in reversed(chain):
            resolved.update(t.config)
        return resolved

    def children(self, tenant_id: str) -> list[Tenant]:
        """Return direct children of *tenant_id*."""
        return [t for t in self._tenants.values() if t.parent_id == tenant_id]

    def all_tenants(self, include_inactive: bool = False) -> list[Tenant]:
        """Return all tenants, optionally including inactive."""
        if include_inactive:
            return list(self._tenants.values())
        return [t for t in self._tenants.values() if t.active]

    def summary(self) -> dict:
        """Return a summary dict."""
        all_t = list(self._tenants.values())
        return {
            "total": len(all_t),
            "active": sum(1 for t in all_t if t.active),
            "inactive": sum(1 for t in all_t if not t.active),
        }
