"""SessionRepairer -- validate and auto-repair session state dicts (stdlib only)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class RepairAction:
    """A single repair that was applied."""

    field: str
    issue: str
    action: str
    old_value: Any
    new_value: Any


@dataclass
class RepairResult:
    """Aggregate result of a repair pass."""

    repaired: bool
    actions: list[RepairAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Type aliases for rule callables
ValidatorFn = Callable[[Any], bool]
RepairFn = Callable[[Any], Any]


# Built-in defaults for required fields
_REQUIRED_DEFAULTS: dict[str, Any] = {
    "session_id": "",
    "created_at": 0.0,
    "messages": [],
    "status": "unknown",
}


class SessionRepairer:
    """Validate and auto-fix common issues in a session-state dict."""

    def __init__(self) -> None:
        # List of (field, validator_fn, repair_fn) tuples
        self._rules: list[tuple[str, ValidatorFn, RepairFn]] = []
        self._install_builtins()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def repair(self, session_data: dict) -> RepairResult:
        """Apply all rules to *session_data* (mutates in place) and return a result."""
        actions: list[RepairAction] = []
        warnings: list[str] = []

        # 1. Missing required fields
        for key, default in _REQUIRED_DEFAULTS.items():
            if key not in session_data:
                actions.append(
                    RepairAction(
                        field=key,
                        issue="missing",
                        action="set_default",
                        old_value=None,
                        new_value=default,
                    )
                )
                session_data[key] = default

        # 2. None values for required fields
        for key, default in _REQUIRED_DEFAULTS.items():
            if session_data.get(key) is None:
                old = session_data[key]
                session_data[key] = default
                actions.append(
                    RepairAction(
                        field=key,
                        issue="none_value",
                        action="replace_none",
                        old_value=old,
                        new_value=default,
                    )
                )

        # 3. Type coercion for known fields
        type_map: dict[str, type] = {
            "session_id": str,
            "created_at": float,
            "messages": list,
            "status": str,
        }
        for key, expected in type_map.items():
            val = session_data.get(key)
            if val is not None and not isinstance(val, expected):
                try:
                    coerced = expected(val)
                    actions.append(
                        RepairAction(
                            field=key,
                            issue="invalid_type",
                            action="coerce",
                            old_value=val,
                            new_value=coerced,
                        )
                    )
                    session_data[key] = coerced
                except (TypeError, ValueError):
                    warnings.append(f"Cannot coerce {key!r} to {expected.__name__}")

        # 4. Custom rules
        for field_name, validator_fn, repair_fn in self._rules:
            val = session_data.get(field_name)
            if not validator_fn(val):
                new_val = repair_fn(val)
                actions.append(
                    RepairAction(
                        field=field_name,
                        issue="custom_rule",
                        action="custom_repair",
                        old_value=val,
                        new_value=new_val,
                    )
                )
                session_data[field_name] = new_val

        return RepairResult(repaired=len(actions) > 0, actions=actions, warnings=warnings)

    def validate(self, session_data: dict) -> list[str]:
        """Return a list of validation error strings (empty == valid)."""
        errors: list[str] = []
        for key in _REQUIRED_DEFAULTS:
            if key not in session_data:
                errors.append(f"missing required field: {key}")
            elif session_data[key] is None:
                errors.append(f"field is None: {key}")

        type_map: dict[str, type] = {
            "session_id": str,
            "created_at": float,
            "messages": list,
            "status": str,
        }
        for key, expected in type_map.items():
            val = session_data.get(key)
            if val is not None and not isinstance(val, expected):
                errors.append(f"invalid type for {key}: expected {expected.__name__}, got {type(val).__name__}")

        for field_name, validator_fn, _ in self._rules:
            val = session_data.get(field_name)
            if not validator_fn(val):
                errors.append(f"custom rule failed for {field_name}")

        return errors

    def is_valid(self, session_data: dict) -> bool:
        """Return *True* if *session_data* passes all validations."""
        return len(self.validate(session_data)) == 0

    def add_rule(self, field: str, validator_fn: ValidatorFn, repair_fn: RepairFn) -> None:
        """Register a custom repair rule."""
        self._rules.append((field, validator_fn, repair_fn))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _install_builtins(self) -> None:
        """Placeholder for built-in rules (handled inline in repair/validate)."""
