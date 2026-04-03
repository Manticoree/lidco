"""MigrationGenerator — generate DB migration scripts."""
from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class Change:
    """A single schema change."""

    type: str  # "add_column", "drop_column", "create_table", "drop_table"
    table: str
    column: str = ""
    column_type: str = ""


class MigrationGenerator:
    """Generate database migration scripts from detected changes."""

    def generate(self, changes: list[Change], framework: str = "alembic") -> str:
        """Generate a migration script for *changes*.

        *framework* is ``"alembic"`` (default) or ``"raw"``.
        """
        if framework == "alembic":
            return self._generate_alembic(changes)
        return self._generate_raw(changes)

    def detect_changes(
        self,
        old_models: list[dict[str, object]],
        new_models: list[dict[str, object]],
    ) -> list[Change]:
        """Compare *old_models* and *new_models* and return a list of :class:`Change`."""
        old_map = {m["name"]: m for m in old_models if "name" in m}
        new_map = {m["name"]: m for m in new_models if "name" in m}

        changes: list[Change] = []

        # Dropped tables
        for name in old_map:
            if name not in new_map:
                changes.append(Change(type="drop_table", table=name))

        # New tables
        for name in new_map:
            if name not in old_map:
                changes.append(Change(type="create_table", table=name))

        # Column diffs for existing tables
        for name in old_map:
            if name not in new_map:
                continue
            old_cols = {c["name"]: c for c in old_map[name].get("columns", []) if "name" in c}  # type: ignore[union-attr]
            new_cols = {c["name"]: c for c in new_map[name].get("columns", []) if "name" in c}  # type: ignore[union-attr]
            for col in old_cols:
                if col not in new_cols:
                    changes.append(
                        Change(
                            type="drop_column",
                            table=name,
                            column=col,
                            column_type=old_cols[col].get("type", ""),
                        )
                    )
            for col in new_cols:
                if col not in old_cols:
                    changes.append(
                        Change(
                            type="add_column",
                            table=name,
                            column=col,
                            column_type=new_cols[col].get("type", ""),
                        )
                    )

        return changes

    def reversible(self, migration: str) -> str:
        """Append a ``downgrade`` stub to an existing migration string."""
        lines = migration.rstrip().split("\n")
        lines.append("")
        lines.append("")
        lines.append("def downgrade() -> None:")
        lines.append('    """Reverse the migration."""')
        lines.append("    pass")
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_alembic(self, changes: list[Change]) -> str:
        revision = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M")
        header = [
            f'"""auto-generated migration {revision}."""',
            "from __future__ import annotations",
            "",
            f'revision = "{revision}"',
            "",
            "",
            "def upgrade() -> None:",
        ]
        body = self._change_lines(changes, indent="    ")
        if not body:
            body = ["    pass"]
        return "\n".join(header + body) + "\n"

    def _generate_raw(self, changes: list[Change]) -> str:
        lines = ["-- auto-generated migration", ""]
        for c in changes:
            lines.append(self._change_to_sql(c))
        lines.append("")
        return "\n".join(lines)

    def _change_lines(self, changes: list[Change], indent: str = "") -> list[str]:
        lines: list[str] = []
        for c in changes:
            if c.type == "create_table":
                lines.append(f'{indent}op.create_table("{c.table}")')
            elif c.type == "drop_table":
                lines.append(f'{indent}op.drop_table("{c.table}")')
            elif c.type == "add_column":
                lines.append(
                    f'{indent}op.add_column("{c.table}", sa.Column("{c.column}", sa.{_sa_type(c.column_type)}))'
                )
            elif c.type == "drop_column":
                lines.append(f'{indent}op.drop_column("{c.table}", "{c.column}")')
        return lines

    def _change_to_sql(self, c: Change) -> str:
        if c.type == "create_table":
            return f"CREATE TABLE {c.table} ();"
        if c.type == "drop_table":
            return f"DROP TABLE {c.table};"
        if c.type == "add_column":
            return f"ALTER TABLE {c.table} ADD COLUMN {c.column} {c.column_type or 'TEXT'};"
        if c.type == "drop_column":
            return f"ALTER TABLE {c.table} DROP COLUMN {c.column};"
        return f"-- unknown change type: {c.type}"


def _sa_type(column_type: str) -> str:
    """Map a simple type string to a SQLAlchemy type name."""
    mapping = {
        "str": "String()",
        "string": "String()",
        "int": "Integer()",
        "integer": "Integer()",
        "float": "Float()",
        "bool": "Boolean()",
        "boolean": "Boolean()",
        "text": "Text()",
        "date": "Date()",
        "datetime": "DateTime()",
    }
    return mapping.get(column_type.lower(), "String()") if column_type else "String()"
