"""SchemaAnalyzer — analyze database schemas, detect relationships, anomalies, generate ER diagrams."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Column:
    """A single column definition."""

    name: str
    type: str = "TEXT"
    primary_key: bool = False
    nullable: bool = True
    unique: bool = False
    foreign_key: str | None = None  # "other_table.column"
    default: Any = None


@dataclass
class Table:
    """A table with columns."""

    name: str
    columns: list[Column] = field(default_factory=list)


@dataclass
class Relationship:
    """A foreign-key relationship between two tables."""

    source_table: str
    source_column: str
    target_table: str
    target_column: str
    type: str = "many-to-one"  # many-to-one, one-to-one


@dataclass
class Index:
    """An index recommendation or existing index."""

    table: str
    columns: list[str]
    unique: bool = False
    name: str = ""


@dataclass
class Anomaly:
    """A schema anomaly or warning."""

    table: str
    severity: str  # "warning", "error", "info"
    message: str


class SchemaAnalyzer:
    """Analyze a database schema for relationships, indexes, anomalies, and generate diagrams."""

    def __init__(self) -> None:
        self._tables: dict[str, Table] = {}

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def add_table(self, name: str, columns: list[Column]) -> Table:
        """Register a table with its columns."""
        table = Table(name=name, columns=list(columns))
        self._tables = {**self._tables, name: table}
        return table

    @property
    def tables(self) -> dict[str, Table]:
        return dict(self._tables)

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def relationships(self) -> list[Relationship]:
        """Detect all foreign-key relationships across tables."""
        rels: list[Relationship] = []
        for table in self._tables.values():
            for col in table.columns:
                if col.foreign_key:
                    parts = col.foreign_key.split(".")
                    if len(parts) == 2:
                        target_table, target_col = parts
                        rel_type = "one-to-one" if col.unique else "many-to-one"
                        rels.append(Relationship(
                            source_table=table.name,
                            source_column=col.name,
                            target_table=target_table,
                            target_column=target_col,
                            type=rel_type,
                        ))
        return rels

    def indexes(self) -> list[Index]:
        """Suggest indexes based on primary keys, foreign keys, and unique constraints."""
        idxs: list[Index] = []
        for table in self._tables.values():
            pk_cols = [c.name for c in table.columns if c.primary_key]
            if pk_cols:
                idxs.append(Index(
                    table=table.name,
                    columns=pk_cols,
                    unique=True,
                    name=f"pk_{table.name}",
                ))
            for col in table.columns:
                if col.foreign_key:
                    idxs.append(Index(
                        table=table.name,
                        columns=[col.name],
                        unique=False,
                        name=f"idx_{table.name}_{col.name}",
                    ))
                elif col.unique and not col.primary_key:
                    idxs.append(Index(
                        table=table.name,
                        columns=[col.name],
                        unique=True,
                        name=f"uq_{table.name}_{col.name}",
                    ))
        return idxs

    def anomalies(self) -> list[Anomaly]:
        """Detect schema anomalies: missing PKs, nullable FKs, orphan FKs, wide tables."""
        issues: list[Anomaly] = []
        for table in self._tables.values():
            # No primary key
            has_pk = any(c.primary_key for c in table.columns)
            if not has_pk:
                issues.append(Anomaly(table.name, "warning", "Table has no primary key."))

            # Nullable FK columns
            for col in table.columns:
                if col.foreign_key and col.nullable:
                    issues.append(Anomaly(
                        table.name, "warning",
                        f"Foreign key column '{col.name}' is nullable.",
                    ))

            # FK targets non-existent table
            for col in table.columns:
                if col.foreign_key:
                    target = col.foreign_key.split(".")[0]
                    if target not in self._tables:
                        issues.append(Anomaly(
                            table.name, "error",
                            f"Foreign key '{col.name}' references unknown table '{target}'.",
                        ))

            # Wide table (>20 columns)
            if len(table.columns) > 20:
                issues.append(Anomaly(
                    table.name, "info",
                    f"Table has {len(table.columns)} columns — consider normalization.",
                ))

            # Duplicate column names
            col_names = [c.name for c in table.columns]
            seen: set[str] = set()
            for cn in col_names:
                if cn in seen:
                    issues.append(Anomaly(table.name, "error", f"Duplicate column name '{cn}'."))
                seen.add(cn)

        return issues

    def er_diagram(self) -> str:
        """Generate a Mermaid ER diagram string."""
        lines: list[str] = ["erDiagram"]
        for table in self._tables.values():
            for col in table.columns:
                pk_mark = " PK" if col.primary_key else ""
                fk_mark = " FK" if col.foreign_key else ""
                lines.append(f"    {table.name} {{")
                # We'll build a block per table instead
                break
            else:
                lines.append(f"    {table.name} {{")
            # Build columns block
            lines.pop()  # remove the partial open

        # Rebuild properly — one block per table
        block_lines: list[str] = ["erDiagram"]
        for table in self._tables.values():
            block_lines.append(f"    {table.name} {{")
            for col in table.columns:
                marks = ""
                if col.primary_key:
                    marks = " PK"
                elif col.foreign_key:
                    marks = " FK"
                block_lines.append(f"        {col.type} {col.name}{marks}")
            block_lines.append("    }")

        # Relationships
        for rel in self.relationships():
            if rel.type == "one-to-one":
                arrow = "||--||"
            else:
                arrow = "||--o{"
            block_lines.append(
                f"    {rel.target_table} {arrow} {rel.source_table} : \"{rel.source_column}\""
            )

        return "\n".join(block_lines)

    def summary(self) -> dict[str, Any]:
        """Return a summary dict of the schema."""
        rels = self.relationships()
        idxs = self.indexes()
        anoms = self.anomalies()
        return {
            "table_count": len(self._tables),
            "tables": list(self._tables.keys()),
            "relationship_count": len(rels),
            "index_count": len(idxs),
            "anomaly_count": len(anoms),
            "anomalies_by_severity": {
                "error": len([a for a in anoms if a.severity == "error"]),
                "warning": len([a for a in anoms if a.severity == "warning"]),
                "info": len([a for a in anoms if a.severity == "info"]),
            },
        }
