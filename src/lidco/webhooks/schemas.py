"""EventSchemaRegistry — register, validate, and version event schemas (stdlib only)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SchemaEntry:
    event_type: str
    schema: dict
    version: str = "1.0.0"


class EventSchemaRegistry:
    """
    Registry for event type schemas.

    Schemas are plain dicts describing required fields and their types:
    ``{"field_name": "str", "count": "int", ...}``
    """

    _TYPE_MAP: Dict[str, type] = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
    }

    def __init__(self) -> None:
        self._schemas: Dict[str, SchemaEntry] = {}

    # -------------------------------------------------------- register

    def register(self, event_type: str, schema: dict, version: str = "1.0.0") -> None:
        """Register (or overwrite) *schema* for *event_type*."""
        self._schemas[event_type] = SchemaEntry(
            event_type=event_type, schema=schema, version=version
        )

    # -------------------------------------------------------- validate

    def validate(self, event_type: str, payload: dict) -> bool:
        """Validate *payload* against the registered schema for *event_type*.

        Returns True if valid (or if no schema is registered — permissive mode).
        """
        entry = self._schemas.get(event_type)
        if entry is None:
            return True  # no schema → always valid

        for field_name, type_name in entry.schema.items():
            if field_name not in payload:
                return False
            expected_type = self._TYPE_MAP.get(str(type_name))
            if expected_type is not None and not isinstance(payload[field_name], expected_type):
                return False
        return True

    # -------------------------------------------------------- list / version

    def list_schemas(self) -> list:
        """Return list of registered event types."""
        return sorted(self._schemas.keys())

    def version(self, event_type: str) -> str:
        """Return version string for *event_type*, or empty string if not found."""
        entry = self._schemas.get(event_type)
        if entry is None:
            return ""
        return entry.version

    def get_schema(self, event_type: str) -> Optional[dict]:
        """Return the schema dict for *event_type*, or None."""
        entry = self._schemas.get(event_type)
        if entry is None:
            return None
        return dict(entry.schema)

    # -------------------------------------------------------- compatibility

    @staticmethod
    def is_compatible(old_version: str, new_version: str) -> bool:
        """Check if *new_version* is backward-compatible with *old_version*.

        Uses semver rules: compatible if major version is the same.
        """
        def parse(v: str) -> List[int]:
            parts = re.findall(r"\d+", v)
            return [int(p) for p in parts[:3]] if parts else [0, 0, 0]

        old_parts = parse(old_version)
        new_parts = parse(new_version)

        # Same major version → compatible
        if old_parts[0] != new_parts[0]:
            return False
        # New version must be >= old version
        return new_parts >= old_parts
