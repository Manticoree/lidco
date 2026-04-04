"""MigrationPlanner2 — plan schema migrations, detect breaking changes, generate rollbacks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MigrationStep:
    """A single migration operation."""

    operation: str  # "add_table", "drop_table", "add_column", "drop_column", "alter_column", "add_index", "drop_index"
    table: str
    column: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    breaking: bool = False


@dataclass
class MigrationPlan:
    """A complete migration plan."""

    steps: list[MigrationStep] = field(default_factory=list)
    version: str = ""
    description: str = ""


@dataclass
class SchemaSnapshot:
    """A simplified schema snapshot for diffing."""

    tables: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    # tables = {"users": {"id": {"type": "INT", "nullable": False}, "name": {"type": "TEXT"}}}


class MigrationPlanner2:
    """Plan migrations between two schema snapshots."""

    def __init__(self) -> None:
        self._plans: list[MigrationPlan] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, old_schema: SchemaSnapshot, new_schema: SchemaSnapshot) -> MigrationPlan:
        """Diff two schemas and produce a migration plan."""
        steps: list[MigrationStep] = []

        old_tables = set(old_schema.tables.keys())
        new_tables = set(new_schema.tables.keys())

        # Dropped tables
        for tbl in sorted(old_tables - new_tables):
            steps.append(MigrationStep(
                operation="drop_table",
                table=tbl,
                breaking=True,
            ))

        # Added tables
        for tbl in sorted(new_tables - old_tables):
            steps.append(MigrationStep(
                operation="add_table",
                table=tbl,
                details={"columns": new_schema.tables[tbl]},
            ))

        # Modified tables
        for tbl in sorted(old_tables & new_tables):
            old_cols = set(old_schema.tables[tbl].keys())
            new_cols = set(new_schema.tables[tbl].keys())

            # Dropped columns
            for col in sorted(old_cols - new_cols):
                steps.append(MigrationStep(
                    operation="drop_column",
                    table=tbl,
                    column=col,
                    breaking=True,
                ))

            # Added columns
            for col in sorted(new_cols - old_cols):
                col_def = new_schema.tables[tbl][col]
                is_breaking = not col_def.get("nullable", True) and "default" not in col_def
                steps.append(MigrationStep(
                    operation="add_column",
                    table=tbl,
                    column=col,
                    details=col_def,
                    breaking=is_breaking,
                ))

            # Altered columns
            for col in sorted(old_cols & new_cols):
                old_def = old_schema.tables[tbl][col]
                new_def = new_schema.tables[tbl][col]
                if old_def != new_def:
                    steps.append(MigrationStep(
                        operation="alter_column",
                        table=tbl,
                        column=col,
                        details={"old": old_def, "new": new_def},
                        breaking=True,
                    ))

        migration = MigrationPlan(steps=steps)
        self._plans = [*self._plans, migration]
        return migration

    def detect_breaking(self, plan: MigrationPlan) -> list[MigrationStep]:
        """Return all breaking steps in a plan."""
        return [s for s in plan.steps if s.breaking]

    def generate_rollback(self, plan: MigrationPlan) -> str:
        """Generate SQL-like rollback statements for a plan (reverse order)."""
        lines: list[str] = ["-- Rollback migration"]
        for step in reversed(plan.steps):
            if step.operation == "add_table":
                lines.append(f"DROP TABLE IF EXISTS {step.table};")
            elif step.operation == "drop_table":
                lines.append(f"CREATE TABLE {step.table} (...);  -- restore from backup")
            elif step.operation == "add_column":
                lines.append(f"ALTER TABLE {step.table} DROP COLUMN {step.column};")
            elif step.operation == "drop_column":
                lines.append(f"ALTER TABLE {step.table} ADD COLUMN {step.column} ...;  -- restore type")
            elif step.operation == "alter_column":
                old_type = step.details.get("old", {}).get("type", "TEXT")
                lines.append(f"ALTER TABLE {step.table} ALTER COLUMN {step.column} TYPE {old_type};")
        return "\n".join(lines)

    def is_safe(self, plan: MigrationPlan) -> bool:
        """Return True if the plan has no breaking changes."""
        return not any(s.breaking for s in plan.steps)

    @property
    def history(self) -> list[MigrationPlan]:
        """All generated plans."""
        return list(self._plans)
