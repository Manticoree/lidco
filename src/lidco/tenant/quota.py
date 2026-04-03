"""Quota enforcer — per-tenant quotas; soft/hard limits; usage tracking."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Quota:
    """A resource quota for a tenant."""

    tenant_id: str
    resource: str  # "tokens" | "cost" | "storage"
    soft_limit: float
    hard_limit: float
    current_usage: float = 0.0


@dataclass(frozen=True)
class QuotaResult:
    """Result of a quota check or consume operation."""

    allowed: bool
    resource: str
    usage: float
    limit: float
    overage: float = 0.0


class QuotaEnforcer:
    """Per-tenant quotas; soft/hard limits; usage tracking; alerts."""

    def __init__(self) -> None:
        self._quotas: dict[tuple[str, str], Quota] = {}  # (tenant_id, resource) -> Quota

    def set_quota(
        self,
        tenant_id: str,
        resource: str,
        soft_limit: float,
        hard_limit: float,
    ) -> Quota:
        """Set or update a quota for *tenant_id* / *resource*."""
        key = (tenant_id, resource)
        existing = self._quotas.get(key)
        if existing is not None:
            existing.soft_limit = soft_limit
            existing.hard_limit = hard_limit
            return existing
        quota = Quota(
            tenant_id=tenant_id,
            resource=resource,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
        )
        self._quotas[key] = quota
        return quota

    def check(self, tenant_id: str, resource: str, amount: float) -> QuotaResult:
        """Check whether *amount* is within the hard limit (does not consume)."""
        key = (tenant_id, resource)
        quota = self._quotas.get(key)
        if quota is None:
            # No quota set — allow
            return QuotaResult(allowed=True, resource=resource, usage=0.0, limit=0.0)
        new_usage = quota.current_usage + amount
        allowed = new_usage <= quota.hard_limit
        overage = max(0.0, new_usage - quota.hard_limit)
        return QuotaResult(
            allowed=allowed,
            resource=resource,
            usage=quota.current_usage,
            limit=quota.hard_limit,
            overage=overage,
        )

    def consume(self, tenant_id: str, resource: str, amount: float) -> QuotaResult:
        """Add *amount* to usage and return result."""
        key = (tenant_id, resource)
        quota = self._quotas.get(key)
        if quota is None:
            return QuotaResult(allowed=True, resource=resource, usage=amount, limit=0.0)
        new_usage = quota.current_usage + amount
        allowed = new_usage <= quota.hard_limit
        overage = max(0.0, new_usage - quota.hard_limit)
        quota.current_usage = new_usage
        return QuotaResult(
            allowed=allowed,
            resource=resource,
            usage=new_usage,
            limit=quota.hard_limit,
            overage=overage,
        )

    def get_usage(self, tenant_id: str, resource: str) -> Quota | None:
        """Get the quota object for inspection."""
        return self._quotas.get((tenant_id, resource))

    def reset(self, tenant_id: str, resource: str | None = None) -> int:
        """Reset usage. If *resource* is None, reset all quotas for tenant. Returns count."""
        count = 0
        for key, quota in self._quotas.items():
            if key[0] == tenant_id and (resource is None or key[1] == resource):
                quota.current_usage = 0.0
                count += 1
        return count

    def over_soft_limit(self) -> list[Quota]:
        """Return all quotas where usage exceeds soft limit."""
        return [q for q in self._quotas.values() if q.current_usage > q.soft_limit]

    def over_hard_limit(self) -> list[Quota]:
        """Return all quotas where usage exceeds hard limit."""
        return [q for q in self._quotas.values() if q.current_usage > q.hard_limit]

    def all_quotas(self, tenant_id: str | None = None) -> list[Quota]:
        """Return all quotas, optionally filtered by tenant."""
        if tenant_id is None:
            return list(self._quotas.values())
        return [q for q in self._quotas.values() if q.tenant_id == tenant_id]

    def summary(self) -> dict:
        """Return a summary dict."""
        return {
            "total_quotas": len(self._quotas),
            "over_soft": len(self.over_soft_limit()),
            "over_hard": len(self.over_hard_limit()),
        }
