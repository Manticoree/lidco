"""Test data factory — generate random test data from schemas (stdlib only)."""
from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Schema:
    """Schema defining fields for test data generation.

    Each field dict should have: ``{name, type}`` and optionally
    ``min``, ``max``, ``choices``.
    """

    fields: list[dict] = field(default_factory=list)


class TestDataFactory:
    """Generate random test data from schemas."""

    def random_string(self, length: int = 10, seed: int | None = None) -> str:
        """Return a random alphabetic string of *length* characters."""
        rng = random.Random(seed)
        return "".join(rng.choices(string.ascii_lowercase, k=length))

    def random_int(self, min_val: int = 0, max_val: int = 1000, seed: int | None = None) -> int:
        """Return a random integer in [*min_val*, *max_val*]."""
        rng = random.Random(seed)
        return rng.randint(min_val, max_val)

    def random_email(self, seed: int | None = None) -> str:
        """Return a random email address."""
        rng = random.Random(seed)
        user = "".join(rng.choices(string.ascii_lowercase, k=8))
        domain = "".join(rng.choices(string.ascii_lowercase, k=6))
        return f"{user}@{domain}.com"

    def generate(self, schema: Schema, count: int = 1, seed: int | None = None) -> list[dict]:
        """Generate *count* data dicts matching *schema*.

        Uses *seed* for reproducibility.
        """
        rng = random.Random(seed)
        results: list[dict] = []
        for _ in range(count):
            row: dict[str, Any] = {}
            for fld in schema.fields:
                name = fld["name"]
                ftype = fld.get("type", "str")
                choices = fld.get("choices")

                if choices:
                    row[name] = rng.choice(choices)
                elif ftype == "int":
                    lo = fld.get("min", 0)
                    hi = fld.get("max", 1000)
                    row[name] = rng.randint(lo, hi)
                elif ftype == "float":
                    lo = fld.get("min", 0.0)
                    hi = fld.get("max", 1.0)
                    row[name] = round(rng.uniform(lo, hi), 4)
                elif ftype == "bool":
                    row[name] = rng.choice([True, False])
                elif ftype == "email":
                    user = "".join(rng.choices(string.ascii_lowercase, k=8))
                    domain = "".join(rng.choices(string.ascii_lowercase, k=6))
                    row[name] = f"{user}@{domain}.com"
                else:
                    # default: str
                    length = fld.get("max", 10)
                    row[name] = "".join(rng.choices(string.ascii_lowercase, k=length))
            results.append(row)
        return results
