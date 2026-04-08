"""Config Validator — validate config files with schema checking.

Cross-reference validation, dependency validation, best practices.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(Enum):
    """Severity of a validation issue."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation finding."""

    path: str
    message: str
    severity: Severity = Severity.ERROR
    rule: str = ""


@dataclass(frozen=True)
class ValidationResult:
    """Aggregated validation result."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    checked_rules: int = 0

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity is Severity.WARNING]


class SchemaRule:
    """A named validation rule that checks a config dict."""

    def __init__(self, name: str, check: Any) -> None:
        self.name = name
        self._check = check

    def run(self, config: dict[str, Any], path: str = "") -> list[ValidationIssue]:
        return list(self._check(config, path))


class ConfigValidator:
    """Validate configuration dicts/files against rules and schemas."""

    def __init__(self) -> None:
        self._rules: list[SchemaRule] = []
        self._schemas: dict[str, dict[str, Any]] = {}
        self._best_practice_checks: list[SchemaRule] = []

    # -- Rule management ---------------------------------------------------

    def add_rule(self, name: str, check: Any) -> None:
        """Add a validation rule.  *check* is ``(config, path) -> Iterable[ValidationIssue]``."""
        self._rules.append(SchemaRule(name, check))

    def add_best_practice(self, name: str, check: Any) -> None:
        """Add a best-practice (warning-level) check."""
        self._best_practice_checks.append(SchemaRule(name, check))

    # -- Schema management -------------------------------------------------

    def register_schema(self, name: str, schema: dict[str, Any]) -> None:
        """Register a JSON-like schema for type/required checking."""
        self._schemas[name] = schema

    def list_schemas(self) -> list[str]:
        return sorted(self._schemas)

    # -- Validation --------------------------------------------------------

    def validate(self, config: dict[str, Any], *, schema_name: str | None = None) -> ValidationResult:
        """Run all rules (and optionally a schema) against *config*."""
        issues: list[ValidationIssue] = []
        checked = 0

        # Schema validation
        if schema_name is not None:
            schema = self._schemas.get(schema_name)
            if schema is None:
                issues.append(ValidationIssue(
                    path="",
                    message=f"Schema not found: {schema_name}",
                    severity=Severity.ERROR,
                    rule="schema_lookup",
                ))
            else:
                issues.extend(self._validate_schema(config, schema, ""))
                checked += 1

        # Custom rules
        for rule in self._rules:
            issues.extend(rule.run(config, ""))
            checked += 1

        # Best practices
        for bp in self._best_practice_checks:
            issues.extend(bp.run(config, ""))
            checked += 1

        valid = not any(i.severity is Severity.ERROR for i in issues)
        return ValidationResult(valid=valid, issues=issues, checked_rules=checked)

    def validate_json_string(self, text: str, *, schema_name: str | None = None) -> ValidationResult:
        """Parse JSON string then validate."""
        try:
            config = json.loads(text)
        except json.JSONDecodeError as exc:
            return ValidationResult(
                valid=False,
                issues=[ValidationIssue(path="", message=f"Invalid JSON: {exc}", severity=Severity.ERROR, rule="json_parse")],
                checked_rules=1,
            )
        if not isinstance(config, dict):
            return ValidationResult(
                valid=False,
                issues=[ValidationIssue(path="", message="Config must be a JSON object", severity=Severity.ERROR, rule="json_type")],
                checked_rules=1,
            )
        return self.validate(config, schema_name=schema_name)

    # -- Cross-reference ---------------------------------------------------

    def cross_validate(self, configs: dict[str, dict[str, Any]]) -> list[ValidationIssue]:
        """Cross-reference multiple named configs for consistency."""
        issues: list[ValidationIssue] = []
        all_keys: dict[str, list[str]] = {}
        for cfg_name, cfg in configs.items():
            for key in self._flatten_keys(cfg):
                all_keys.setdefault(key, []).append(cfg_name)

        # Warn about keys present in some but not all configs
        config_names = set(configs)
        for key, present_in in all_keys.items():
            missing = config_names - set(present_in)
            if missing and len(present_in) > 0:
                issues.append(ValidationIssue(
                    path=key,
                    message=f"Key '{key}' missing in: {', '.join(sorted(missing))}",
                    severity=Severity.WARNING,
                    rule="cross_reference",
                ))
        return issues

    # -- Dependency validation ---------------------------------------------

    def validate_dependencies(self, config: dict[str, Any], dependencies: dict[str, list[str]]) -> list[ValidationIssue]:
        """If key A is set, ensure keys in dependencies[A] are also set."""
        issues: list[ValidationIssue] = []
        flat = self._flatten_keys(config)
        for key, deps in dependencies.items():
            if key in flat:
                for dep in deps:
                    if dep not in flat:
                        issues.append(ValidationIssue(
                            path=key,
                            message=f"Key '{key}' requires '{dep}' to be set",
                            severity=Severity.ERROR,
                            rule="dependency",
                        ))
        return issues

    # -- Schema helpers ----------------------------------------------------

    def _validate_schema(self, config: dict[str, Any], schema: dict[str, Any], path: str) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        # Check required fields
        required = schema.get("required", [])
        for req in required:
            if req not in config:
                full = f"{path}.{req}" if path else req
                issues.append(ValidationIssue(
                    path=full,
                    message=f"Missing required field: {req}",
                    severity=Severity.ERROR,
                    rule="schema_required",
                ))

        # Check types
        properties = schema.get("properties", {})
        for key, prop in properties.items():
            if key in config:
                expected_type = prop.get("type")
                full = f"{path}.{key}" if path else key
                if expected_type and not self._type_matches(config[key], expected_type):
                    issues.append(ValidationIssue(
                        path=full,
                        message=f"Expected type '{expected_type}' for '{key}', got '{type(config[key]).__name__}'",
                        severity=Severity.ERROR,
                        rule="schema_type",
                    ))

        return issues

    @staticmethod
    def _type_matches(value: Any, expected: str) -> bool:
        mapping: dict[str, type | tuple[type, ...]] = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        return isinstance(value, mapping.get(expected, object))

    @staticmethod
    def _flatten_keys(d: dict[str, Any], prefix: str = "") -> set[str]:
        keys: set[str] = set()
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else k
            keys.add(full)
            if isinstance(v, dict):
                keys.update(ConfigValidator._flatten_keys(v, full))
        return keys

    # -- Built-in best practices -------------------------------------------

    @staticmethod
    def with_defaults() -> ConfigValidator:
        """Return a validator with common best-practice checks pre-loaded."""
        v = ConfigValidator()

        def _check_no_empty_strings(config: dict[str, Any], path: str) -> list[ValidationIssue]:
            issues: list[ValidationIssue] = []
            for key, val in config.items():
                full = f"{path}.{key}" if path else key
                if isinstance(val, str) and val == "":
                    issues.append(ValidationIssue(
                        path=full,
                        message=f"Empty string value for '{key}'",
                        severity=Severity.WARNING,
                        rule="no_empty_strings",
                    ))
                elif isinstance(val, dict):
                    issues.extend(_check_no_empty_strings(val, full))
            return issues

        def _check_no_placeholder_secrets(config: dict[str, Any], path: str) -> list[ValidationIssue]:
            issues: list[ValidationIssue] = []
            secret_pattern = re.compile(r"(password|secret|token|api_key)", re.IGNORECASE)
            placeholder_pattern = re.compile(r"^(TODO|CHANGEME|FIXME|xxx+|placeholder)$", re.IGNORECASE)
            for key, val in config.items():
                full = f"{path}.{key}" if path else key
                if secret_pattern.search(key) and isinstance(val, str) and placeholder_pattern.match(val):
                    issues.append(ValidationIssue(
                        path=full,
                        message=f"Placeholder value for secret '{key}'",
                        severity=Severity.ERROR,
                        rule="no_placeholder_secrets",
                    ))
                elif isinstance(val, dict):
                    issues.extend(_check_no_placeholder_secrets(val, full))
            return issues

        v.add_best_practice("no_empty_strings", _check_no_empty_strings)
        v.add_rule("no_placeholder_secrets", _check_no_placeholder_secrets)
        return v
