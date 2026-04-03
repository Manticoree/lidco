"""UsageTracker — Per-key usage tracking with daily/monthly aggregation and quota."""
from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UsageRecord:
    key_id: str
    provider: str
    tokens: int
    cost: float
    timestamp: float


class UsageTracker:
    """Track API usage per key with aggregation and quota enforcement."""

    def __init__(self, quota: dict[str, int] | None = None) -> None:
        self._quota: dict[str, int] = dict(quota) if quota else {}
        self._records: list[UsageRecord] = []

    def record(self, key_id: str, provider: str, tokens: int, cost: float) -> UsageRecord:
        """Record a usage event."""
        rec = UsageRecord(
            key_id=key_id,
            provider=provider,
            tokens=tokens,
            cost=cost,
            timestamp=time.time(),
        )
        self._records.append(rec)
        return rec

    def daily(self, provider: str | None = None, date: str | None = None) -> dict:
        """Aggregate tokens and cost by day. Optionally filter by provider/date."""
        filtered = self._filter(provider)
        buckets: dict[str, dict] = {}
        for rec in filtered:
            day = datetime.fromtimestamp(rec.timestamp).strftime("%Y-%m-%d")
            if date is not None and day != date:
                continue
            if day not in buckets:
                buckets[day] = {"tokens": 0, "cost": 0.0}
            buckets[day]["tokens"] += rec.tokens
            buckets[day]["cost"] += rec.cost
        return buckets

    def monthly(self, provider: str | None = None) -> dict:
        """Aggregate tokens and cost by month."""
        filtered = self._filter(provider)
        buckets: dict[str, dict] = {}
        for rec in filtered:
            month = datetime.fromtimestamp(rec.timestamp).strftime("%Y-%m")
            if month not in buckets:
                buckets[month] = {"tokens": 0, "cost": 0.0}
            buckets[month]["tokens"] += rec.tokens
            buckets[month]["cost"] += rec.cost
        return buckets

    def quota_check(self, provider: str) -> dict:
        """Check usage against quota for a provider."""
        used = sum(r.tokens for r in self._records if r.provider == provider)
        limit = self._quota.get(provider, 0)
        remaining = max(0, limit - used)
        percentage = (used / limit * 100) if limit > 0 else 0.0
        return {
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "percentage": round(percentage, 2),
        }

    def export_csv(self) -> str:
        """Export all records to a CSV string."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["key_id", "provider", "tokens", "cost", "timestamp"])
        for rec in self._records:
            writer.writerow([rec.key_id, rec.provider, rec.tokens, rec.cost, rec.timestamp])
        return buf.getvalue()

    def total(self, provider: str | None = None) -> dict:
        """Total tokens and cost, optionally filtered by provider."""
        filtered = self._filter(provider)
        return {
            "tokens": sum(r.tokens for r in filtered),
            "cost": sum(r.cost for r in filtered),
        }

    def records(self, provider: str | None = None) -> list[UsageRecord]:
        """Return all records, optionally filtered by provider."""
        return self._filter(provider)

    def summary(self) -> dict:
        """Summary of usage state."""
        t = self.total()
        return {
            "total_records": len(self._records),
            "total_tokens": t["tokens"],
            "total_cost": t["cost"],
            "providers": list({r.provider for r in self._records}),
        }

    def _filter(self, provider: str | None) -> list[UsageRecord]:
        if provider is None:
            return list(self._records)
        return [r for r in self._records if r.provider == provider]
