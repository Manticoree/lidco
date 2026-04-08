"""
Q345 — API Contract Stability: Config Schema Validator.

Validates configuration schemas — ensures defaults exist, rejects unknown
keys, checks type coercibility, and extracts schemas from dataclass source.
"""
from __future__ import annotations

import ast

# Map of Python type names to their corresponding Python types for coercion checks
_COERCE_MAP: dict[str, type] = {
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
}


class ConfigSchemaValidator:
    """Validate configuration objects against a schema."""

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # validate_defaults
    # ------------------------------------------------------------------

    def validate_defaults(self, schema: dict) -> list[dict]:
        """Check that all config fields have default values.

        ``schema`` has a ``"fields"`` list of dicts:
        ``{"name": str, "type": str, "default": any (optional), "required": bool}``.

        Returns a list of dicts with ``"field"``, ``"has_default"``,
        ``"required"``, ``"suggestion"``.
        """
        results: list[dict] = []

        for field in schema.get("fields", []):
            name = field.get("name", "")
            required = bool(field.get("required", False))
            has_default = "default" in field

            if has_default:
                suggestion = f"Field '{name}' has a default value."
            elif required:
                suggestion = (
                    f"Required field '{name}' has no default. "
                    "Ensure it is always provided in config."
                )
            else:
                suggestion = (
                    f"Optional field '{name}' has no default. "
                    "Consider adding a sensible default value."
                )

            results.append(
                {
                    "field": name,
                    "has_default": has_default,
                    "required": required,
                    "suggestion": suggestion,
                }
            )

        return results

    # ------------------------------------------------------------------
    # reject_unknown_keys
    # ------------------------------------------------------------------

    def reject_unknown_keys(
        self, config: dict, schema: dict
    ) -> list[str]:
        """Return a list of keys present in ``config`` but not defined in ``schema``.

        ``schema`` has a ``"fields"`` list with ``"name"`` entries.
        """
        known = {f.get("name", "") for f in schema.get("fields", [])}
        return sorted(key for key in config if key not in known)

    # ------------------------------------------------------------------
    # check_type_coercion
    # ------------------------------------------------------------------

    def check_type_coercion(
        self, config: dict, schema: dict
    ) -> list[dict]:
        """Check type safety of each config value against the schema.

        Returns a list of dicts with ``"field"``, ``"expected_type"``,
        ``"actual_type"``, ``"coercible"`` (bool), ``"suggestion"``.
        """
        field_map: dict[str, dict] = {
            f.get("name", ""): f for f in schema.get("fields", [])
        }

        results: list[dict] = []

        for key, value in config.items():
            if key not in field_map:
                continue

            expected_type_name = field_map[key].get("type", "str")
            actual_type_name = type(value).__name__

            if actual_type_name == expected_type_name:
                coercible = True
                suggestion = f"Field '{key}' matches expected type '{expected_type_name}'."
            else:
                coercible = self._is_coercible(value, expected_type_name)
                if coercible:
                    suggestion = (
                        f"Field '{key}' has type '{actual_type_name}' but "
                        f"can be coerced to '{expected_type_name}'."
                    )
                else:
                    suggestion = (
                        f"Field '{key}' has type '{actual_type_name}' which "
                        f"cannot be coerced to '{expected_type_name}'. "
                        "Fix the config value."
                    )

            results.append(
                {
                    "field": key,
                    "expected_type": expected_type_name,
                    "actual_type": actual_type_name,
                    "coercible": coercible,
                    "suggestion": suggestion,
                }
            )

        return results

    def _is_coercible(self, value: object, target_type_name: str) -> bool:
        """Return True if ``value`` can be coerced to ``target_type_name``."""
        target = _COERCE_MAP.get(target_type_name)
        if target is None:
            return False
        try:
            target(value)  # type: ignore[call-arg]
            return True
        except (ValueError, TypeError):
            return False

    # ------------------------------------------------------------------
    # generate_schema
    # ------------------------------------------------------------------

    def generate_schema(self, source_code: str) -> dict:
        """Extract a config schema from Python dataclass source code.

        Returns ``{"fields": [{"name", "type", "default" (if present),
        "required"}]}``.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return {"fields": []}

        fields: list[dict] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not self._is_dataclass(node):
                continue
            for stmt in node.body:
                field = self._extract_field(stmt)
                if field is not None:
                    fields.append(field)

        return {"fields": fields}

    def _is_dataclass(self, node: ast.ClassDef) -> bool:
        for dec in node.decorator_list:
            name = ast.unparse(dec) if hasattr(ast, "unparse") else ""
            if "dataclass" in name:
                return True
        return False

    def _extract_field(self, stmt: ast.stmt) -> dict | None:
        """Extract a field definition from a class body statement."""
        if not isinstance(stmt, ast.AnnAssign):
            return None

        target = stmt.target
        if not isinstance(target, ast.Name):
            return None

        name = target.id
        # Skip dunder attributes
        if name.startswith("__"):
            return None

        type_name = (
            ast.unparse(stmt.annotation)
            if hasattr(ast, "unparse") and stmt.annotation
            else "Any"
        )

        result: dict = {
            "name": name,
            "type": type_name,
            "required": stmt.value is None,
        }

        if stmt.value is not None:
            default_val = self._eval_default(stmt.value)
            if default_val is not None:
                result["default"] = default_val

        return result

    def _eval_default(self, node: ast.expr) -> object:
        """Safely evaluate a simple default value AST node."""
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError):
            # For complex defaults (e.g. field(default_factory=list)), return placeholder
            return ast.unparse(node) if hasattr(ast, "unparse") else None
