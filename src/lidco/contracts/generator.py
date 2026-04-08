"""Contract Generator — generate contracts from API usage.

Records interactions, infers schemas, and produces Pact-compatible output.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from lidco.contracts.definitions import (
    ContractDefinition,
    EndpointSchema,
    FieldSchema,
    FieldType,
)


@dataclass(frozen=True)
class RecordedInteraction:
    """A single recorded HTTP interaction."""

    method: str
    path: str
    request_body: dict[str, Any] = field(default_factory=dict)
    response_body: dict[str, Any] = field(default_factory=dict)
    status_code: int = 200
    description: str = ""

    def interaction_id(self) -> str:
        """Stable identifier based on method + path."""
        raw = f"{self.method.upper()} {self.path}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]


def _infer_field_type(value: Any) -> FieldType:
    """Infer a FieldType from a Python value."""
    if isinstance(value, bool):
        return FieldType.BOOLEAN
    if isinstance(value, int):
        return FieldType.INTEGER
    if isinstance(value, float):
        return FieldType.FLOAT
    if isinstance(value, str):
        return FieldType.STRING
    if isinstance(value, (list, tuple)):
        return FieldType.ARRAY
    if isinstance(value, dict):
        return FieldType.OBJECT
    if value is None:
        return FieldType.NULL
    return FieldType.ANY


def _infer_fields(body: dict[str, Any]) -> tuple[FieldSchema, ...]:
    """Infer field schemas from a dict."""
    fields: list[FieldSchema] = []
    for key, val in sorted(body.items()):
        ft = _infer_field_type(val)
        items_type = None
        if ft == FieldType.ARRAY and val:
            items_type = _infer_field_type(val[0])
        props: tuple[FieldSchema, ...] = ()
        if ft == FieldType.OBJECT and isinstance(val, dict):
            props = _infer_fields(val)
        fields.append(FieldSchema(
            name=key,
            field_type=ft,
            required=True,
            items_type=items_type,
            properties=props,
        ))
    return tuple(fields)


class ContractGenerator:
    """Generate contract definitions from recorded interactions."""

    def __init__(self) -> None:
        self._interactions: list[RecordedInteraction] = []

    @property
    def interaction_count(self) -> int:
        return len(self._interactions)

    def record(self, interaction: RecordedInteraction) -> None:
        """Record a new interaction (appends; original list is not mutated)."""
        self._interactions = [*self._interactions, interaction]

    def clear(self) -> None:
        """Clear all recorded interactions."""
        self._interactions = []

    def generate(
        self,
        name: str,
        version: str,
        provider: str,
        consumer: str,
    ) -> ContractDefinition:
        """Generate a ``ContractDefinition`` from recorded interactions."""
        seen: dict[tuple[str, str], RecordedInteraction] = {}
        for ix in self._interactions:
            key = (ix.method.upper(), ix.path)
            seen[key] = ix  # last-write-wins

        endpoints: list[EndpointSchema] = []
        for (method, path), ix in sorted(seen.items()):
            req_fields = _infer_fields(ix.request_body)
            resp_fields = _infer_fields(ix.response_body)
            endpoints.append(EndpointSchema(
                method=method,
                path=path,
                request_fields=req_fields,
                response_fields=resp_fields,
                status_code=ix.status_code,
                description=ix.description,
            ))

        return ContractDefinition(
            name=name,
            version=version,
            provider=provider,
            consumer=consumer,
            endpoints=tuple(endpoints),
        )

    def to_pact(
        self,
        provider: str,
        consumer: str,
    ) -> dict[str, Any]:
        """Export recorded interactions as a Pact-compatible JSON dict."""
        interactions: list[dict[str, Any]] = []
        for ix in self._interactions:
            interactions.append({
                "description": ix.description or f"{ix.method.upper()} {ix.path}",
                "request": {
                    "method": ix.method.upper(),
                    "path": ix.path,
                    "body": ix.request_body if ix.request_body else None,
                },
                "response": {
                    "status": ix.status_code,
                    "body": ix.response_body if ix.response_body else None,
                },
            })

        return {
            "provider": {"name": provider},
            "consumer": {"name": consumer},
            "interactions": interactions,
            "metadata": {"pactSpecification": {"version": "2.0.0"}},
        }

    def to_json(
        self,
        name: str,
        version: str,
        provider: str,
        consumer: str,
        *,
        indent: int = 2,
    ) -> str:
        """Generate the contract and serialise to a JSON string."""
        contract = self.generate(name, version, provider, consumer)
        return json.dumps(contract.to_dict(), indent=indent)
