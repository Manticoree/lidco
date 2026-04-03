"""Tenant analytics — per-tenant usage stats; cost allocation; comparison."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class UsageStat:
    """A single usage record."""

    tenant_id: str
    resource: str
    value: float
    timestamp: float


class TenantAnalytics:
    """Per-tenant usage stats; cost allocation; comparison."""

    def __init__(self) -> None:
        self._records: list[UsageStat] = []

    def record(self, tenant_id: str, resource: str, value: float) -> UsageStat:
        """Record a usage stat."""
        stat = UsageStat(
            tenant_id=tenant_id,
            resource=resource,
            value=value,
            timestamp=time.time(),
        )
        self._records.append(stat)
        return stat

    def total(self, tenant_id: str, resource: str | None = None) -> dict:
        """Total per resource for a tenant."""
        totals: dict[str, float] = {}
        for r in self._records:
            if r.tenant_id != tenant_id:
                continue
            if resource is not None and r.resource != resource:
                continue
            totals[r.resource] = totals.get(r.resource, 0.0) + r.value
        return totals

    def compare(self, tenant_ids: list[str], resource: str) -> dict:
        """Side-by-side totals for a resource across tenants."""
        result: dict[str, float] = {}
        for tid in tenant_ids:
            total = 0.0
            for r in self._records:
                if r.tenant_id == tid and r.resource == resource:
                    total += r.value
            result[tid] = total
        return result

    def top_consumers(self, resource: str, limit: int = 10) -> list[tuple[str, float]]:
        """Top consumers for a resource, sorted descending."""
        totals: dict[str, float] = {}
        for r in self._records:
            if r.resource == resource:
                totals[r.tenant_id] = totals.get(r.tenant_id, 0.0) + r.value
        ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)
        return ranked[:limit]

    def history(
        self, tenant_id: str, resource: str | None = None
    ) -> list[UsageStat]:
        """Return usage history for a tenant."""
        return [
            r
            for r in self._records
            if r.tenant_id == tenant_id
            and (resource is None or r.resource == resource)
        ]

    def cost_allocation(self) -> dict[str, float]:
        """Total cost per tenant (resource='cost')."""
        alloc: dict[str, float] = {}
        for r in self._records:
            if r.resource == "cost":
                alloc[r.tenant_id] = alloc.get(r.tenant_id, 0.0) + r.value
        return alloc

    def summary(self) -> dict:
        """Return a summary dict."""
        tenants = {r.tenant_id for r in self._records}
        resources = {r.resource for r in self._records}
        return {
            "total_records": len(self._records),
            "tenants_tracked": len(tenants),
            "resources_tracked": len(resources),
        }
