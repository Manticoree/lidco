"""Contract Definitions — define API contracts with request/response schemas.

Provides ``ContractDefinition``, ``EndpointSchema``, ``FieldSchema``, and
``ContractRegistry`` for managing provider/consumer roles and versioning.
"""

from __future__ import annotations

import copy
import enum
import re
from dataclasses import dataclass, field
from typing import Any


class FieldType(enum.Enum):
    """Supported field types in a schema."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"
    ANY = "any"


class Role(enum.Enum):
    """Participant role in a contract."""

    PROVIDER = "provider"
    CONSUMER = "consumer"


@dataclass(frozen=True)
class FieldSchema:
    """Schema for a single field."""

    name: str
    field_type: FieldType
    required: bool = True
    description: str = ""
    items_type: FieldType | None = None  # for ARRAY
    properties: tuple[FieldSchema, ...] = ()  # for OBJECT
    default: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict."""
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.field_type.value,
            "required": self.required,
        }
        if self.description:
            d["description"] = self.description
        if self.items_type is not None:
            d["items_type"] = self.items_type.value
        if self.properties:
            d["properties"] = [p.to_dict() for p in self.properties]
        if self.default is not None:
            d["default"] = self.default
        return d

    @staticmethod
    def from_dict(data: dict[str, Any]) -> FieldSchema:
        """Deserialise from a plain dict."""
        props = tuple(
            FieldSchema.from_dict(p) for p in data.get("properties", [])
        )
        items = (
            FieldType(data["items_type"]) if "items_type" in data else None
        )
        return FieldSchema(
            name=data["name"],
            field_type=FieldType(data["type"]),
            required=data.get("required", True),
            description=data.get("description", ""),
            items_type=items,
            properties=props,
            default=data.get("default"),
        )


@dataclass(frozen=True)
class EndpointSchema:
    """Request/response schema for a single API endpoint."""

    method: str
    path: str
    request_fields: tuple[FieldSchema, ...] = ()
    response_fields: tuple[FieldSchema, ...] = ()
    description: str = ""
    status_code: int = 200

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "method": self.method,
            "path": self.path,
            "status_code": self.status_code,
        }
        if self.description:
            d["description"] = self.description
        if self.request_fields:
            d["request"] = [f.to_dict() for f in self.request_fields]
        if self.response_fields:
            d["response"] = [f.to_dict() for f in self.response_fields]
        return d

    @staticmethod
    def from_dict(data: dict[str, Any]) -> EndpointSchema:
        req = tuple(
            FieldSchema.from_dict(f) for f in data.get("request", [])
        )
        resp = tuple(
            FieldSchema.from_dict(f) for f in data.get("response", [])
        )
        return EndpointSchema(
            method=data["method"],
            path=data["path"],
            request_fields=req,
            response_fields=resp,
            description=data.get("description", ""),
            status_code=data.get("status_code", 200),
        )


_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class ContractDefinition:
    """A versioned API contract between a provider and consumer."""

    name: str
    version: str
    provider: str
    consumer: str
    endpoints: tuple[EndpointSchema, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _VERSION_RE.match(self.version):
            raise ValueError(
                f"Invalid version '{self.version}' — expected semver X.Y.Z"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "provider": self.provider,
            "consumer": self.consumer,
            "endpoints": [e.to_dict() for e in self.endpoints],
            "metadata": copy.deepcopy(self.metadata),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ContractDefinition:
        eps = tuple(
            EndpointSchema.from_dict(e) for e in data.get("endpoints", [])
        )
        return ContractDefinition(
            name=data["name"],
            version=data["version"],
            provider=data["provider"],
            consumer=data["consumer"],
            endpoints=eps,
            metadata=data.get("metadata", {}),
        )


class ContractRegistry:
    """In-memory registry for contract definitions, keyed by (name, version)."""

    def __init__(self) -> None:
        self._contracts: dict[tuple[str, str], ContractDefinition] = {}

    # -- queries ----------------------------------------------------------

    @property
    def count(self) -> int:
        return len(self._contracts)

    def get(self, name: str, version: str) -> ContractDefinition | None:
        return self._contracts.get((name, version))

    def list_all(self) -> list[ContractDefinition]:
        return sorted(
            self._contracts.values(), key=lambda c: (c.name, c.version)
        )

    def list_versions(self, name: str) -> list[str]:
        return sorted(
            v for (n, v) in self._contracts if n == name
        )

    def find_by_provider(self, provider: str) -> list[ContractDefinition]:
        return [c for c in self._contracts.values() if c.provider == provider]

    def find_by_consumer(self, consumer: str) -> list[ContractDefinition]:
        return [c for c in self._contracts.values() if c.consumer == consumer]

    # -- mutations (return new state via copy) ----------------------------

    def register(self, contract: ContractDefinition) -> ContractRegistry:
        """Register a contract. Returns a *new* registry with the contract added."""
        new = ContractRegistry()
        new._contracts = {**self._contracts, (contract.name, contract.version): contract}
        return new

    def remove(self, name: str, version: str) -> ContractRegistry:
        """Remove a contract. Returns a *new* registry without it."""
        new = ContractRegistry()
        new._contracts = {
            k: v for k, v in self._contracts.items() if k != (name, version)
        }
        return new

    def export_all(self) -> list[dict[str, Any]]:
        """Export all contracts as a list of dicts."""
        return [c.to_dict() for c in self.list_all()]

    @staticmethod
    def import_all(data: list[dict[str, Any]]) -> ContractRegistry:
        """Import contracts from a list of dicts."""
        reg = ContractRegistry()
        for d in data:
            contract = ContractDefinition.from_dict(d)
            reg = reg.register(contract)
        return reg
