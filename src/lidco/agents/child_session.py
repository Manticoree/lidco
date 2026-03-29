"""ChildSessionSpawner — spawn child sessions with output schema validation (stdlib only)."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class SchemaValidationError(Exception):
    """Raised when child session output fails schema validation."""


_TYPE_MAP: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "list": list,
    "dict": dict,
    "bool": bool,
}


@dataclass
class OutputSchema:
    fields: dict[str, str]  # field_name -> type_name
    required: list[str] = field(default_factory=list)


@dataclass
class ChildSessionResult:
    session_id: str
    prompt: str
    raw_result: str
    validated: dict[str, Any]
    schema: OutputSchema


class ChildSessionHandle:
    """Handle for a spawned child session, with schema validation."""

    def __init__(self, session_id: str, prompt: str, schema: OutputSchema) -> None:
        self.session_id = session_id
        self.prompt = prompt
        self.schema = schema

    def validate(self, raw_result: str) -> dict[str, Any]:
        """Parse raw JSON and validate against schema. Raises SchemaValidationError."""
        try:
            data = json.loads(raw_result)
        except (json.JSONDecodeError, TypeError) as exc:
            raise SchemaValidationError(f"Invalid JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise SchemaValidationError(f"Expected JSON object, got {type(data).__name__}")

        # Check required fields
        for req in self.schema.required:
            if req not in data:
                raise SchemaValidationError(f"Missing required field: {req}")

        # Type-check present fields that are declared in the schema
        validated: dict[str, Any] = {}
        for key, type_name in self.schema.fields.items():
            if key not in data:
                continue
            expected_type = _TYPE_MAP.get(type_name)
            if expected_type is not None and not isinstance(data[key], expected_type):
                # Special case: int accepts bool in Python, but we want strict
                if expected_type is int and isinstance(data[key], bool):
                    raise SchemaValidationError(
                        f"Field '{key}': expected {type_name}, got {type(data[key]).__name__}"
                    )
                raise SchemaValidationError(
                    f"Field '{key}': expected {type_name}, got {type(data[key]).__name__}"
                )
            validated[key] = data[key]

        return validated

    def complete(self, raw_result: str) -> ChildSessionResult:
        """Validate and return a ChildSessionResult."""
        validated = self.validate(raw_result)
        return ChildSessionResult(
            session_id=self.session_id,
            prompt=self.prompt,
            raw_result=raw_result,
            validated=validated,
            schema=self.schema,
        )


class ChildSessionSpawner:
    """Spawn child sessions with optional memory inheritance."""

    def __init__(self, memory_store=None) -> None:
        self._memory_store = memory_store

    def spawn(self, prompt: str, schema: Optional[OutputSchema] = None) -> ChildSessionHandle:
        """Create a new ChildSessionHandle with unique session_id."""
        session_id = uuid.uuid4().hex[:16]
        if schema is None:
            schema = OutputSchema(fields={})
        return ChildSessionHandle(session_id=session_id, prompt=prompt, schema=schema)

    def spawn_and_run(
        self,
        prompt: str,
        schema: OutputSchema,
        llm_fn: Callable[[str], str],
    ) -> ChildSessionResult:
        """Spawn, call llm_fn(prompt), validate result, return ChildSessionResult."""
        handle = self.spawn(prompt, schema=schema)
        raw = llm_fn(prompt)
        return handle.complete(raw)
