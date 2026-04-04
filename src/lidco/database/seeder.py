"""DataSeeder — generate deterministic seed data for database tables."""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SeedColumn:
    """Column definition for seeding."""

    name: str
    type: str = "text"  # "text", "int", "float", "bool", "email", "name", "date"
    nullable: bool = False
    unique: bool = False
    foreign_key: str | None = None  # "table.column"


@dataclass
class SeedTable:
    """Table registered for seeding."""

    name: str
    columns: list[SeedColumn] = field(default_factory=list)


class DataSeeder:
    """Generate realistic seed data for database tables."""

    _FIRST_NAMES = [
        "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry",
        "Iris", "Jack", "Kate", "Leo", "Mia", "Noah", "Olivia", "Paul",
    ]
    _LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson",
    ]
    _DOMAINS = ["example.com", "test.org", "demo.net", "sample.io"]
    _WORDS = [
        "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
        "hotel", "india", "juliet", "kilo", "lima", "mike", "november",
    ]

    def __init__(self) -> None:
        self._tables: dict[str, SeedTable] = {}
        self._rng: random.Random = random.Random(42)
        self._generated: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Table registration
    # ------------------------------------------------------------------

    def add_table(self, name: str, columns: list[SeedColumn]) -> SeedTable:
        """Register a table for seeding."""
        table = SeedTable(name=name, columns=list(columns))
        self._tables = {**self._tables, name: table}
        return table

    # ------------------------------------------------------------------
    # Seed control
    # ------------------------------------------------------------------

    def deterministic(self, seed: int) -> None:
        """Set the random seed for reproducible output."""
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self, table: str, count: int) -> list[dict[str, Any]]:
        """Generate *count* rows for the given table."""
        if table not in self._tables:
            raise ValueError(f"Table '{table}' not registered.")

        tbl = self._tables[table]
        rows: list[dict[str, Any]] = []
        used_values: dict[str, set[Any]] = {
            c.name: set() for c in tbl.columns if c.unique
        }

        for i in range(count):
            row: dict[str, Any] = {}
            for col in tbl.columns:
                if col.nullable and self._rng.random() < 0.1:
                    row[col.name] = None
                    continue
                value = self._gen_value(col, i)
                # Ensure uniqueness
                if col.unique:
                    attempts = 0
                    while value in used_values[col.name] and attempts < 100:
                        value = self._gen_value(col, i + attempts + count)
                        attempts += 1
                    used_values[col.name].add(value)
                row[col.name] = value
            rows.append(row)

        self._generated = {**self._generated, table: rows}
        return rows

    def with_references(self, table: str, fk_table: str) -> list[dict[str, Any]]:
        """Re-generate rows for *table*, filling FK columns with values from *fk_table*."""
        if table not in self._tables:
            raise ValueError(f"Table '{table}' not registered.")
        if fk_table not in self._generated:
            raise ValueError(f"No generated data for FK table '{fk_table}'. Generate it first.")

        tbl = self._tables[table]
        fk_rows = self._generated[fk_table]
        existing = self._generated.get(table, [])

        if not existing:
            existing = self.generate(table, len(fk_rows))

        updated: list[dict[str, Any]] = []
        for row in existing:
            new_row = dict(row)
            for col in tbl.columns:
                if col.foreign_key and col.foreign_key.startswith(fk_table + "."):
                    fk_col = col.foreign_key.split(".")[1]
                    ref_row = self._rng.choice(fk_rows)
                    if fk_col in ref_row:
                        new_row[col.name] = ref_row[fk_col]
            updated.append(new_row)

        self._generated = {**self._generated, table: updated}
        return updated

    # ------------------------------------------------------------------
    # Value generators
    # ------------------------------------------------------------------

    def _gen_value(self, col: SeedColumn, index: int) -> Any:
        t = col.type.lower()
        if t == "int":
            return self._rng.randint(1, 100_000)
        if t == "float":
            return round(self._rng.uniform(0.0, 10_000.0), 2)
        if t == "bool":
            return self._rng.choice([True, False])
        if t == "email":
            first = self._rng.choice(self._FIRST_NAMES).lower()
            domain = self._rng.choice(self._DOMAINS)
            num = self._rng.randint(1, 9999)
            return f"{first}{num}@{domain}"
        if t == "name":
            return f"{self._rng.choice(self._FIRST_NAMES)} {self._rng.choice(self._LAST_NAMES)}"
        if t == "date":
            year = self._rng.randint(2020, 2026)
            month = self._rng.randint(1, 12)
            day = self._rng.randint(1, 28)
            return f"{year}-{month:02d}-{day:02d}"
        # Default: text
        word_count = self._rng.randint(1, 4)
        words = [self._rng.choice(self._WORDS) for _ in range(word_count)]
        return " ".join(words)
