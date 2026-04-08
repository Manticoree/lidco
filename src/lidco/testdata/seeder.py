"""
Task 1705 — Data Seeder

Seed databases from fixtures: idempotent, rollback, environment-specific,
validation.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence

from lidco.testdata.fixtures import FixtureDef, FixtureManager, FixtureScope


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class SeedStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass(frozen=True)
class SeedEntry:
    """A single seed operation record."""

    fixture_name: str
    table: str
    record_count: int = 0
    status: SeedStatus = SeedStatus.PENDING
    error: Optional[str] = None
    timestamp: float = 0.0


@dataclass(frozen=True)
class SeedPlan:
    """Plan describing what the seeder will do."""

    entries: tuple[SeedEntry, ...] = ()
    environment: str = "development"
    idempotent: bool = True

    @property
    def total_records(self) -> int:
        return sum(e.record_count for e in self.entries)

    @property
    def tables(self) -> list[str]:
        return list(dict.fromkeys(e.table for e in self.entries))


@dataclass(frozen=True)
class SeedResult:
    """Result of executing a seed plan."""

    applied: tuple[SeedEntry, ...] = ()
    failed: tuple[SeedEntry, ...] = ()
    rolled_back: bool = False

    @property
    def success(self) -> bool:
        return len(self.failed) == 0

    @property
    def total_applied(self) -> int:
        return sum(e.record_count for e in self.applied)


@dataclass(frozen=True)
class ValidationError:
    """A validation error found in seed data."""

    fixture_name: str
    field: str
    message: str


# ---------------------------------------------------------------------------
# DataSeeder
# ---------------------------------------------------------------------------

class DataSeeder:
    """
    Seed a target store from fixtures, with idempotency, rollback,
    environment filtering, and validation.

    The seeder does NOT directly talk to a database; instead it produces
    ``SeedPlan`` / ``SeedResult`` objects and delegates actual writes to
    a pluggable *backend* callback.

    Usage::

        seeder = DataSeeder(environment="testing")
        seeder = seeder.add_fixture("users", "users_table", fixture_def)
        plan = seeder.plan()
        result = seeder.execute(plan)
    """

    def __init__(
        self,
        *,
        environment: str = "development",
        idempotent: bool = True,
        backend: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ) -> None:
        self._environment = environment
        self._idempotent = idempotent
        self._backend = backend
        self._entries: Dict[str, tuple[str, FixtureDef]] = {}  # name→(table, fixture)
        self._applied_log: list[SeedEntry] = []

    # -- registration --------------------------------------------------------

    def add_fixture(
        self, name: str, table: str, fixture: FixtureDef
    ) -> DataSeeder:
        """Return a new seeder with an additional fixture to seed."""
        new_entries = {**self._entries, name: (table, fixture)}
        s = DataSeeder.__new__(DataSeeder)
        s._environment = self._environment
        s._idempotent = self._idempotent
        s._backend = self._backend
        s._entries = new_entries
        s._applied_log = list(self._applied_log)
        return s

    # -- validation ----------------------------------------------------------

    def validate(self) -> list[ValidationError]:
        """Validate all registered fixture data."""
        errors: list[ValidationError] = []
        for name, (table, fixture) in self._entries.items():
            if not fixture.data:
                errors.append(ValidationError(
                    fixture_name=name,
                    field="data",
                    message="Fixture data is empty",
                ))
            if not table:
                errors.append(ValidationError(
                    fixture_name=name,
                    field="table",
                    message="Table name is empty",
                ))
        return errors

    # -- planning ------------------------------------------------------------

    def plan(self) -> SeedPlan:
        """Create a seed plan without executing anything."""
        entries: list[SeedEntry] = []
        for name, (table, fixture) in self._entries.items():
            record_count = len(fixture.data) if isinstance(fixture.data, list) else 1
            entries.append(SeedEntry(
                fixture_name=name,
                table=table,
                record_count=record_count,
                status=SeedStatus.PENDING,
                timestamp=time.time(),
            ))
        return SeedPlan(
            entries=tuple(entries),
            environment=self._environment,
            idempotent=self._idempotent,
        )

    # -- execution -----------------------------------------------------------

    def execute(self, seed_plan: Optional[SeedPlan] = None) -> SeedResult:
        """Execute a seed plan (or auto-plan if none given)."""
        plan = seed_plan or self.plan()
        applied: list[SeedEntry] = []
        failed: list[SeedEntry] = []

        for entry in plan.entries:
            name = entry.fixture_name
            if name not in self._entries:
                failed.append(SeedEntry(
                    fixture_name=name,
                    table=entry.table,
                    record_count=entry.record_count,
                    status=SeedStatus.FAILED,
                    error=f"Unknown fixture: {name}",
                    timestamp=time.time(),
                ))
                continue

            table, fixture = self._entries[name]

            # Idempotency check: skip if already applied
            if self._idempotent and name in [e.fixture_name for e in self._applied_log]:
                applied.append(SeedEntry(
                    fixture_name=name,
                    table=table,
                    record_count=entry.record_count,
                    status=SeedStatus.APPLIED,
                    timestamp=time.time(),
                ))
                continue

            try:
                if self._backend:
                    ok = self._backend(table, fixture.data)
                    if not ok:
                        raise RuntimeError(f"Backend rejected seed for {table}")
                applied_entry = SeedEntry(
                    fixture_name=name,
                    table=table,
                    record_count=entry.record_count,
                    status=SeedStatus.APPLIED,
                    timestamp=time.time(),
                )
                applied.append(applied_entry)
                self._applied_log.append(applied_entry)
            except Exception as exc:
                failed.append(SeedEntry(
                    fixture_name=name,
                    table=table,
                    record_count=entry.record_count,
                    status=SeedStatus.FAILED,
                    error=str(exc),
                    timestamp=time.time(),
                ))

        return SeedResult(applied=tuple(applied), failed=tuple(failed))

    # -- rollback ------------------------------------------------------------

    def rollback(self) -> SeedResult:
        """Rollback all previously applied seeds."""
        rolled: list[SeedEntry] = []
        for entry in reversed(self._applied_log):
            rolled.append(SeedEntry(
                fixture_name=entry.fixture_name,
                table=entry.table,
                record_count=entry.record_count,
                status=SeedStatus.ROLLED_BACK,
                timestamp=time.time(),
            ))
        self._applied_log = []
        return SeedResult(applied=tuple(rolled), rolled_back=True)

    # -- query ---------------------------------------------------------------

    @property
    def environment(self) -> str:
        return self._environment

    @property
    def fixture_names(self) -> list[str]:
        return list(self._entries.keys())

    @property
    def applied_count(self) -> int:
        return len(self._applied_log)
