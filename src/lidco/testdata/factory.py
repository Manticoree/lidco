"""
Task 1702 — Data Factory

Generate test data with faker-like capabilities; type-aware; relationships;
constraints; deterministic seed.
"""

from __future__ import annotations

import hashlib
import random
import string
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldSpec:
    """Specification for a single field in a data factory."""

    name: str
    field_type: str  # "string", "int", "float", "bool", "email", "name", "uuid", "choice", "ref"
    nullable: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    choices: Optional[Sequence[str]] = None
    pattern: Optional[str] = None  # for "string" — length hint
    ref_factory: Optional[str] = None  # for "ref" — name of related factory
    default: Any = None
    constraints: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class FactorySchema:
    """Schema definition for a data factory."""

    name: str
    fields: tuple[FieldSpec, ...] = ()

    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]


@dataclass(frozen=True)
class GeneratedRecord:
    """A single generated record."""

    schema_name: str
    data: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass(frozen=True)
class GenerationResult:
    """Result of a batch generation."""

    schema_name: str
    records: tuple[GeneratedRecord, ...] = ()
    seed: int = 0

    @property
    def count(self) -> int:
        return len(self.records)


# ---------------------------------------------------------------------------
# Name / word pools (stdlib-only faker-like)
# ---------------------------------------------------------------------------

_FIRST_NAMES = (
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Hank",
    "Ivy", "Jack", "Karen", "Leo", "Mona", "Nate", "Olivia", "Paul",
    "Quinn", "Rose", "Sam", "Tina", "Uma", "Vince", "Wendy", "Xander",
    "Yara", "Zane",
)

_LAST_NAMES = (
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Wilson", "Anderson", "Taylor",
    "Thomas", "Moore", "Jackson", "Martin", "Lee", "Perez", "Clark",
)

_DOMAINS = (
    "example.com", "test.org", "demo.net", "sample.io", "mock.dev",
)

_WORDS = (
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
    "hotel", "india", "juliet", "kilo", "lima", "mike", "november",
    "oscar", "papa", "quebec", "romeo", "sierra", "tango",
)


# ---------------------------------------------------------------------------
# DataFactory
# ---------------------------------------------------------------------------

class DataFactory:
    """
    Generate test data using deterministic random seeds.

    Usage::

        factory = DataFactory(seed=42)
        factory.register_schema(FactorySchema("user", (
            FieldSpec("id", "int", min_value=1, max_value=99999),
            FieldSpec("name", "name"),
            FieldSpec("email", "email"),
        )))
        result = factory.generate("user", count=5)
    """

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed
        self._schemas: Dict[str, FactorySchema] = {}
        self._custom_generators: Dict[str, Callable[[random.Random], Any]] = {}
        self._rng = random.Random(seed)

    # -- schema management ---------------------------------------------------

    def register_schema(self, schema: FactorySchema) -> DataFactory:
        """Register a schema (returns self for chaining)."""
        return DataFactory._with_schema(self, schema)

    @staticmethod
    def _with_schema(factory: DataFactory, schema: FactorySchema) -> DataFactory:
        new_schemas = {**factory._schemas, schema.name: schema}
        result = DataFactory.__new__(DataFactory)
        result._seed = factory._seed
        result._schemas = new_schemas
        result._custom_generators = dict(factory._custom_generators)
        result._rng = random.Random(factory._seed)
        return result

    def register_generator(self, type_name: str, gen: Callable[[random.Random], Any]) -> DataFactory:
        """Register a custom type generator."""
        new_gens = {**self._custom_generators, type_name: gen}
        result = DataFactory.__new__(DataFactory)
        result._seed = self._seed
        result._schemas = dict(self._schemas)
        result._custom_generators = new_gens
        result._rng = random.Random(self._seed)
        return result

    @property
    def schemas(self) -> Dict[str, FactorySchema]:
        return dict(self._schemas)

    @property
    def seed(self) -> int:
        return self._seed

    # -- generation ----------------------------------------------------------

    def generate(self, schema_name: str, count: int = 1) -> GenerationResult:
        """Generate *count* records for the given schema."""
        if schema_name not in self._schemas:
            raise ValueError(f"Unknown schema: {schema_name}")

        schema = self._schemas[schema_name]
        rng = random.Random(self._seed)
        records: list[GeneratedRecord] = []

        for _ in range(count):
            data = self._generate_record(schema, rng)
            records.append(GeneratedRecord(schema_name=schema_name, data=data))

        return GenerationResult(
            schema_name=schema_name,
            records=tuple(records),
            seed=self._seed,
        )

    def generate_one(self, schema_name: str) -> GeneratedRecord:
        """Convenience: generate a single record."""
        return self.generate(schema_name, count=1).records[0]

    # -- private helpers -----------------------------------------------------

    def _generate_record(self, schema: FactorySchema, rng: random.Random) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        for fld in schema.fields:
            if fld.nullable and rng.random() < 0.1:
                data[fld.name] = None
                continue
            data[fld.name] = self._generate_field(fld, rng)
        return data

    def _generate_field(self, fld: FieldSpec, rng: random.Random) -> Any:
        if fld.default is not None:
            return fld.default

        ft = fld.field_type

        # custom generator?
        if ft in self._custom_generators:
            return self._custom_generators[ft](rng)

        if ft == "string":
            length = int(fld.min_value) if fld.min_value else 8
            return "".join(rng.choices(string.ascii_lowercase, k=length))

        if ft == "int":
            lo = int(fld.min_value) if fld.min_value is not None else 0
            hi = int(fld.max_value) if fld.max_value is not None else 1_000_000
            return rng.randint(lo, hi)

        if ft == "float":
            lo = fld.min_value if fld.min_value is not None else 0.0
            hi = fld.max_value if fld.max_value is not None else 1_000_000.0
            return round(rng.uniform(lo, hi), 4)

        if ft == "bool":
            return rng.choice([True, False])

        if ft == "name":
            return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"

        if ft == "email":
            first = rng.choice(_FIRST_NAMES).lower()
            last = rng.choice(_LAST_NAMES).lower()
            domain = rng.choice(_DOMAINS)
            return f"{first}.{last}@{domain}"

        if ft == "uuid":
            hex_str = hashlib.md5(
                f"{self._seed}-{rng.random()}".encode()
            ).hexdigest()
            return (
                f"{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}"
                f"-{hex_str[16:20]}-{hex_str[20:32]}"
            )

        if ft == "choice":
            if not fld.choices:
                raise ValueError(f"Field {fld.name!r}: 'choice' type requires choices")
            return rng.choice(list(fld.choices))

        if ft == "ref":
            if not fld.ref_factory or fld.ref_factory not in self._schemas:
                raise ValueError(
                    f"Field {fld.name!r}: 'ref' type requires valid ref_factory"
                )
            ref_schema = self._schemas[fld.ref_factory]
            return self._generate_record(ref_schema, rng)

        raise ValueError(f"Unknown field type: {ft}")

    # -- determinism helpers -------------------------------------------------

    def reset(self) -> DataFactory:
        """Return a new factory with the RNG reset to the original seed."""
        result = DataFactory.__new__(DataFactory)
        result._seed = self._seed
        result._schemas = dict(self._schemas)
        result._custom_generators = dict(self._custom_generators)
        result._rng = random.Random(self._seed)
        return result
