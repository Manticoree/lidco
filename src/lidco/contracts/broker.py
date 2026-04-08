"""Contract Broker — store, share, and manage contracts.

Provides version matrix, compatibility dashboard, and webhook notifications
when contracts break.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from lidco.contracts.definitions import ContractDefinition, ContractRegistry
from lidco.contracts.verifier import ContractVerifier, VerificationResult


@dataclass(frozen=True)
class WebhookConfig:
    """Webhook endpoint configuration."""

    url: str
    events: tuple[str, ...] = ("break",)
    enabled: bool = True


@dataclass(frozen=True)
class MatrixEntry:
    """One cell of the version compatibility matrix."""

    provider: str
    consumer: str
    contract_name: str
    version: str
    compatible: bool
    verified_at: float = 0.0


@dataclass(frozen=True)
class DashboardEntry:
    """Summary entry for the compatibility dashboard."""

    contract_name: str
    total_versions: int
    compatible_count: int
    incompatible_count: int
    latest_version: str


class ContractBroker:
    """Central broker that stores contracts and tracks compatibility."""

    def __init__(self) -> None:
        self._registry: ContractRegistry = ContractRegistry()
        self._verifier: ContractVerifier = ContractVerifier()
        self._matrix: list[MatrixEntry] = []
        self._webhooks: list[WebhookConfig] = []
        self._webhook_log: list[dict[str, Any]] = []

    # -- contract storage -------------------------------------------------

    @property
    def contract_count(self) -> int:
        return self._registry.count

    def publish(self, contract: ContractDefinition) -> None:
        """Publish a contract to the broker."""
        self._registry = self._registry.register(contract)

    def get_contract(
        self, name: str, version: str
    ) -> ContractDefinition | None:
        return self._registry.get(name, version)

    def list_contracts(self) -> list[ContractDefinition]:
        return self._registry.list_all()

    def list_versions(self, name: str) -> list[str]:
        return self._registry.list_versions(name)

    # -- version matrix ---------------------------------------------------

    def record_verification(
        self,
        contract: ContractDefinition,
        result: VerificationResult,
    ) -> None:
        """Record a verification result in the matrix."""
        entry = MatrixEntry(
            provider=contract.provider,
            consumer=contract.consumer,
            contract_name=contract.name,
            version=contract.version,
            compatible=result.passed,
            verified_at=time.time(),
        )
        self._matrix = [*self._matrix, entry]

        if not result.passed:
            self._fire_webhook("break", {
                "contract": contract.name,
                "version": contract.version,
                "provider": contract.provider,
                "consumer": contract.consumer,
                "errors": result.error_count,
            })

    def version_matrix(
        self, contract_name: str | None = None
    ) -> list[MatrixEntry]:
        """Return the version matrix, optionally filtered by contract name."""
        if contract_name is None:
            return list(self._matrix)
        return [e for e in self._matrix if e.contract_name == contract_name]

    # -- compatibility dashboard ------------------------------------------

    def dashboard(self) -> list[DashboardEntry]:
        """Build a compatibility dashboard across all contracts."""
        names: dict[str, list[MatrixEntry]] = {}
        for entry in self._matrix:
            names.setdefault(entry.contract_name, []).append(entry)

        result: list[DashboardEntry] = []
        for name in sorted(names):
            entries = names[name]
            versions = sorted({e.version for e in entries})
            compat = sum(1 for e in entries if e.compatible)
            incompat = sum(1 for e in entries if not e.compatible)
            result.append(DashboardEntry(
                contract_name=name,
                total_versions=len(versions),
                compatible_count=compat,
                incompatible_count=incompat,
                latest_version=versions[-1] if versions else "",
            ))
        return result

    # -- webhooks ---------------------------------------------------------

    def add_webhook(self, webhook: WebhookConfig) -> None:
        """Register a webhook endpoint."""
        self._webhooks = [*self._webhooks, webhook]

    @property
    def webhook_count(self) -> int:
        return len(self._webhooks)

    @property
    def webhook_log(self) -> list[dict[str, Any]]:
        return list(self._webhook_log)

    def _fire_webhook(self, event: str, payload: dict[str, Any]) -> None:
        """Log webhook invocations (actual HTTP delivery is external)."""
        for wh in self._webhooks:
            if not wh.enabled:
                continue
            if event not in wh.events:
                continue
            self._webhook_log = [
                *self._webhook_log,
                {
                    "url": wh.url,
                    "event": event,
                    "payload": payload,
                    "timestamp": time.time(),
                },
            ]

    # -- persistence ------------------------------------------------------

    def export_json(self) -> str:
        """Export all contracts as JSON."""
        return json.dumps(self._registry.export_all(), indent=2)

    def import_json(self, data: str) -> int:
        """Import contracts from a JSON string. Returns count imported."""
        items = json.loads(data)
        for item in items:
            contract = ContractDefinition.from_dict(item)
            self._registry = self._registry.register(contract)
        return len(items)

    def save(self, path: str | Path) -> None:
        """Persist contracts to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.export_json(), encoding="utf-8")

    def load(self, path: str | Path) -> int:
        """Load contracts from a JSON file. Returns count loaded."""
        p = Path(path)
        if not p.exists():
            return 0
        return self.import_json(p.read_text(encoding="utf-8"))
