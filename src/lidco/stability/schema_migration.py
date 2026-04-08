"""
Schema Migration Validator.

Validates database schema upgrades for compatibility, backward compatibility,
data preservation risks, and generates rollback SQL statements.
"""
from __future__ import annotations

import hashlib


class SchemaMigrationValidator:
    """Validates schema migrations for safety and compatibility."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_upgrade(self, old_schema: dict, new_schema: dict) -> dict:
        """Validate a schema upgrade from old_schema to new_schema.

        Schemas have a "tables" key mapping table_name -> list of column dicts:
        {"name": str, "type": str, "nullable": bool}.

        Returns:
            dict with keys:
                "compatible" (bool): True if upgrade is safe
                "breaking_changes" (list): descriptions of breaking changes
                "additions" (list): descriptions of new tables/columns
                "warnings" (list): non-breaking but notable changes
        """
        breaking: list[str] = []
        additions: list[str] = []
        warnings: list[str] = []

        old_tables: dict = old_schema.get("tables", {})
        new_tables: dict = new_schema.get("tables", {})

        # Check for dropped tables
        for table in old_tables:
            if table not in new_tables:
                breaking.append(f"Table '{table}' was dropped")

        # Check for new tables
        for table in new_tables:
            if table not in old_tables:
                additions.append(f"New table '{table}' added")

        # Check column-level changes for shared tables
        for table in old_tables:
            if table not in new_tables:
                continue
            old_cols = {c["name"]: c for c in old_tables[table]}
            new_cols = {c["name"]: c for c in new_tables[table]}

            # Dropped columns
            for col in old_cols:
                if col not in new_cols:
                    breaking.append(f"Column '{table}.{col}' was dropped")

            # New columns
            for col in new_cols:
                if col not in old_cols:
                    new_col = new_cols[col]
                    if not new_col.get("nullable", True):
                        breaking.append(
                            f"Column '{table}.{col}' added as NOT NULL without default"
                        )
                    else:
                        additions.append(f"Column '{table}.{col}' added (nullable)")

            # Type changes and nullability changes
            for col in old_cols:
                if col not in new_cols:
                    continue
                old_col = old_cols[col]
                new_col = new_cols[col]

                old_type = old_col.get("type", "").upper()
                new_type = new_col.get("type", "").upper()
                if old_type != new_type:
                    if _is_safe_type_change(old_type, new_type):
                        warnings.append(
                            f"Column '{table}.{col}' type changed from {old_type} to {new_type} (safe widening)"
                        )
                    else:
                        breaking.append(
                            f"Column '{table}.{col}' type changed from {old_type} to {new_type}"
                        )

                old_nullable = old_col.get("nullable", True)
                new_nullable = new_col.get("nullable", True)
                if old_nullable and not new_nullable:
                    breaking.append(
                        f"Column '{table}.{col}' changed from nullable to NOT NULL"
                    )
                elif not old_nullable and new_nullable:
                    warnings.append(
                        f"Column '{table}.{col}' relaxed from NOT NULL to nullable"
                    )

        return {
            "compatible": len(breaking) == 0,
            "breaking_changes": breaking,
            "additions": additions,
            "warnings": warnings,
        }

    def check_backward_compat(self, old_schema: dict, new_schema: dict) -> list[dict]:
        """Check if the new schema is backward compatible with old.

        Returns list of dicts with "table", "column", "issue", "severity".
        Severity: "critical" | "warning" | "info"
        """
        issues: list[dict] = []
        old_tables: dict = old_schema.get("tables", {})
        new_tables: dict = new_schema.get("tables", {})

        for table in old_tables:
            if table not in new_tables:
                issues.append({
                    "table": table,
                    "column": "*",
                    "issue": f"Table '{table}' missing in new schema — old clients will break",
                    "severity": "critical",
                })
                continue

            old_cols = {c["name"]: c for c in old_tables[table]}
            new_cols = {c["name"]: c for c in new_tables[table]}

            for col, old_col in old_cols.items():
                if col not in new_cols:
                    issues.append({
                        "table": table,
                        "column": col,
                        "issue": f"Column '{col}' removed — existing queries will fail",
                        "severity": "critical",
                    })
                    continue

                new_col = new_cols[col]
                old_type = old_col.get("type", "").upper()
                new_type = new_col.get("type", "").upper()
                if old_type != new_type:
                    severity = "warning" if _is_safe_type_change(old_type, new_type) else "critical"
                    issues.append({
                        "table": table,
                        "column": col,
                        "issue": f"Type changed from {old_type} to {new_type}",
                        "severity": severity,
                    })

                old_nullable = old_col.get("nullable", True)
                new_nullable = new_col.get("nullable", True)
                if old_nullable and not new_nullable:
                    issues.append({
                        "table": table,
                        "column": col,
                        "issue": "Column became NOT NULL — inserts without this column will fail",
                        "severity": "critical",
                    })

        return issues

    def verify_data_preservation(self, old_schema: dict, new_schema: dict) -> list[dict]:
        """Verify no data loss risks in migration.

        Returns list of dicts with "table", "column", "risk", "suggestion".
        """
        risks: list[dict] = []
        old_tables: dict = old_schema.get("tables", {})
        new_tables: dict = new_schema.get("tables", {})

        for table in old_tables:
            if table not in new_tables:
                risks.append({
                    "table": table,
                    "column": "*",
                    "risk": "All data in table will be lost",
                    "suggestion": f"Add DROP TABLE {table} to rollback and ensure data is migrated first",
                })
                continue

            old_cols = {c["name"]: c for c in old_tables[table]}
            new_cols = {c["name"]: c for c in new_tables[table]}

            for col, old_col in old_cols.items():
                if col not in new_cols:
                    risks.append({
                        "table": table,
                        "column": col,
                        "risk": "Column data will be permanently lost",
                        "suggestion": f"Backup data from {table}.{col} before migration",
                    })
                    continue

                new_col = new_cols[col]
                old_type = old_col.get("type", "").upper()
                new_type = new_col.get("type", "").upper()
                if old_type != new_type and not _is_safe_type_change(old_type, new_type):
                    risks.append({
                        "table": table,
                        "column": col,
                        "risk": f"Data may be truncated or lost converting {old_type} to {new_type}",
                        "suggestion": f"Validate all existing {table}.{col} values fit {new_type} before migration",
                    })

                old_nullable = old_col.get("nullable", True)
                new_nullable = new_col.get("nullable", True)
                if old_nullable and not new_nullable:
                    risks.append({
                        "table": table,
                        "column": col,
                        "risk": "Existing NULL values will violate new NOT NULL constraint",
                        "suggestion": f"Update NULLs in {table}.{col} before adding NOT NULL constraint",
                    })

        return risks

    def generate_rollback(self, old_schema: dict, new_schema: dict) -> list[str]:
        """Generate SQL rollback statements to revert new_schema to old_schema.

        Returns list of SQL statement strings.
        """
        statements: list[str] = []
        old_tables: dict = old_schema.get("tables", {})
        new_tables: dict = new_schema.get("tables", {})

        # Drop tables that were added in the new schema
        for table in new_tables:
            if table not in old_tables:
                statements.append(f"DROP TABLE IF EXISTS {table};")

        # For tables that existed before, restore dropped columns / revert changes
        for table in old_tables:
            if table not in new_tables:
                # Recreate dropped table
                col_defs = _columns_to_sql(old_tables[table])
                statements.append(f"CREATE TABLE IF NOT EXISTS {table} ({col_defs});")
                continue

            old_cols = {c["name"]: c for c in old_tables[table]}
            new_cols = {c["name"]: c for c in new_tables[table]}

            # Drop new columns that were added
            for col in new_cols:
                if col not in old_cols:
                    statements.append(f"ALTER TABLE {table} DROP COLUMN {col};")

            # Restore dropped columns
            for col, old_col in old_cols.items():
                if col not in new_cols:
                    col_def = _column_to_sql(old_col)
                    statements.append(f"ALTER TABLE {table} ADD COLUMN {col_def};")
                    continue

                # Revert type changes
                new_col = new_cols[col]
                if old_col.get("type") != new_col.get("type"):
                    old_type = old_col.get("type", "TEXT")
                    statements.append(
                        f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {old_type};"
                    )

                # Revert nullability changes
                old_nullable = old_col.get("nullable", True)
                new_nullable = new_col.get("nullable", True)
                if old_nullable != new_nullable:
                    if old_nullable:
                        statements.append(
                            f"ALTER TABLE {table} ALTER COLUMN {col} DROP NOT NULL;"
                        )
                    else:
                        statements.append(
                            f"ALTER TABLE {table} ALTER COLUMN {col} SET NOT NULL;"
                        )

        return statements


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAFE_WIDENINGS: set[tuple[str, str]] = {
    ("INT", "BIGINT"),
    ("INT", "NUMERIC"),
    ("INT", "FLOAT"),
    ("INT", "TEXT"),
    ("VARCHAR", "TEXT"),
    ("CHAR", "VARCHAR"),
    ("CHAR", "TEXT"),
    ("FLOAT", "DOUBLE"),
    ("FLOAT", "NUMERIC"),
    ("SMALLINT", "INT"),
    ("SMALLINT", "BIGINT"),
}


def _is_safe_type_change(old_type: str, new_type: str) -> bool:
    """Return True if the type change is a safe widening."""
    return (old_type, new_type) in _SAFE_WIDENINGS


def _column_to_sql(col: dict) -> str:
    name = col.get("name", "col")
    ctype = col.get("type", "TEXT")
    nullable = col.get("nullable", True)
    null_clause = "" if nullable else " NOT NULL"
    return f"{name} {ctype}{null_clause}"


def _columns_to_sql(cols: list[dict]) -> str:
    return ", ".join(_column_to_sql(c) for c in cols)
