"""Q128 — Configuration Profiles: SchemaValidator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationError:
    field: str
    message: str


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)


_TYPE_MAP: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
}


class SchemaValidator:
    """Simple schema validator.

    Schema format::

        {
            "field_name": {
                "type": "str",      # optional
                "required": True,   # optional, default False
                "default": "value", # optional
            }
        }
    """

    def __init__(self, schema: dict) -> None:
        self._schema = schema

    def validate(self, data: dict) -> ValidationResult:
        errors: list[ValidationError] = []
        for fname, fdef in self._schema.items():
            required = fdef.get("required", False)
            if fname not in data:
                if required:
                    errors.append(
                        ValidationError(fname, f"Field '{fname}' is required")
                    )
                continue
            value = data[fname]
            type_name = fdef.get("type")
            if type_name:
                expected = _TYPE_MAP.get(type_name)
                if expected and not isinstance(value, expected):
                    errors.append(
                        ValidationError(
                            fname,
                            f"Field '{fname}' expected {type_name}, got {type(value).__name__}",
                        )
                    )
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def coerce(self, data: dict) -> dict:
        result = dict(data)
        for fname, fdef in self._schema.items():
            if fname not in result:
                if "default" in fdef:
                    result[fname] = fdef["default"]
                continue
            type_name = fdef.get("type")
            if type_name:
                expected = _TYPE_MAP.get(type_name)
                if expected and not isinstance(result[fname], expected):
                    try:
                        result[fname] = expected(result[fname])
                    except (ValueError, TypeError):
                        pass
        return result

    def required_fields(self) -> list[str]:
        return [
            fname
            for fname, fdef in self._schema.items()
            if fdef.get("required", False)
        ]
