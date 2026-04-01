"""Versioned migration runner."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field


class MigrationStatus(str, enum.Enum):
    """Status of a migration."""

    PENDING = "pending"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass(frozen=True)
class Migration:
    """A single migration definition."""

    version: str
    name: str
    up_sql: str = ""
    down_sql: str = ""
    applied_at: float | None = None
    status: MigrationStatus = MigrationStatus.PENDING


@dataclass(frozen=True)
class MigrationResult:
    """Result of running a migration."""

    version: str
    success: bool
    direction: str  # "up" | "down"
    error: str = ""
    duration_ms: float = 0.0


class MigrationError(Exception):
    """Error during migration execution."""


class MigrationRunner:
    """Runs versioned migrations up/down."""

    def __init__(self) -> None:
        self._migrations: dict[str, Migration] = {}
        self._order: list[str] = []
        self._history: list[MigrationResult] = []

    def add(self, migration: Migration) -> None:
        """Register a migration."""
        self._migrations[migration.version] = migration
        if migration.version not in self._order:
            self._order.append(migration.version)

    def run_up(self, version: str | None = None) -> list[MigrationResult]:
        """Run a single migration (by version) or all pending migrations up."""
        results: list[MigrationResult] = []
        if version is not None:
            if version not in self._migrations:
                raise MigrationError(f"Migration '{version}' not found.")
            results.append(self._apply_up(version))
        else:
            for v in self._order:
                m = self._migrations[v]
                if m.status == MigrationStatus.PENDING:
                    results.append(self._apply_up(v))
        return results

    def run_down(self, version: str) -> MigrationResult:
        """Rollback a single migration."""
        if version not in self._migrations:
            raise MigrationError(f"Migration '{version}' not found.")
        return self._apply_down(version)

    def dry_run(self, version: str | None = None) -> list[str]:
        """Return list of SQL statements that would run."""
        statements: list[str] = []
        if version is not None:
            if version not in self._migrations:
                raise MigrationError(f"Migration '{version}' not found.")
            m = self._migrations[version]
            if m.up_sql:
                statements.append(m.up_sql)
        else:
            for v in self._order:
                m = self._migrations[v]
                if m.status == MigrationStatus.PENDING and m.up_sql:
                    statements.append(m.up_sql)
        return statements

    def get_status(self) -> list[Migration]:
        """Return all migrations with current status."""
        return [self._migrations[v] for v in self._order]

    def history(self) -> list[MigrationResult]:
        """Return history of executed migration results."""
        return list(self._history)

    def pending(self) -> list[Migration]:
        """Return migrations that are still pending."""
        return [
            self._migrations[v]
            for v in self._order
            if self._migrations[v].status == MigrationStatus.PENDING
        ]

    def latest_version(self) -> str | None:
        """Return the latest applied version, or None."""
        applied = [
            v for v in self._order
            if self._migrations[v].status == MigrationStatus.APPLIED
        ]
        return applied[-1] if applied else None

    def rollback_all(self) -> list[MigrationResult]:
        """Rollback all applied migrations in reverse order."""
        results: list[MigrationResult] = []
        for v in reversed(self._order):
            m = self._migrations[v]
            if m.status == MigrationStatus.APPLIED:
                results.append(self._apply_down(v))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_up(self, version: str) -> MigrationResult:
        m = self._migrations[version]
        start = time.monotonic()
        try:
            # Simulate execution (no real DB)
            elapsed = (time.monotonic() - start) * 1000
            self._migrations[version] = Migration(
                version=m.version,
                name=m.name,
                up_sql=m.up_sql,
                down_sql=m.down_sql,
                applied_at=time.time(),
                status=MigrationStatus.APPLIED,
            )
            result = MigrationResult(
                version=version, success=True, direction="up", duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            self._migrations[version] = Migration(
                version=m.version,
                name=m.name,
                up_sql=m.up_sql,
                down_sql=m.down_sql,
                applied_at=None,
                status=MigrationStatus.FAILED,
            )
            result = MigrationResult(
                version=version, success=False, direction="up",
                error=str(exc), duration_ms=elapsed,
            )
        self._history.append(result)
        return result

    def _apply_down(self, version: str) -> MigrationResult:
        m = self._migrations[version]
        start = time.monotonic()
        try:
            elapsed = (time.monotonic() - start) * 1000
            self._migrations[version] = Migration(
                version=m.version,
                name=m.name,
                up_sql=m.up_sql,
                down_sql=m.down_sql,
                applied_at=None,
                status=MigrationStatus.ROLLED_BACK,
            )
            result = MigrationResult(
                version=version, success=True, direction="down", duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            result = MigrationResult(
                version=version, success=False, direction="down",
                error=str(exc), duration_ms=elapsed,
            )
        self._history.append(result)
        return result
