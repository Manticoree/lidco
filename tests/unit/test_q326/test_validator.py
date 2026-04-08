"""Tests for lidco.configmgmt.validator — Config Validator."""

from __future__ import annotations

import unittest

from lidco.configmgmt.validator import (
    ConfigValidator,
    SchemaRule,
    Severity,
    ValidationIssue,
    ValidationResult,
)


class TestConfigValidator(unittest.TestCase):
    """Tests for ConfigValidator."""

    def setUp(self) -> None:
        self.validator = ConfigValidator()

    # -- Basic validation --------------------------------------------------

    def test_validate_empty_config_no_rules(self) -> None:
        result = self.validator.validate({})
        self.assertTrue(result.valid)
        self.assertEqual(result.issues, [])

    def test_validate_with_custom_rule(self) -> None:
        def check_port(cfg: dict, path: str) -> list[ValidationIssue]:
            if "port" in cfg and not isinstance(cfg["port"], int):
                return [ValidationIssue(path="port", message="port must be int", severity=Severity.ERROR, rule="port_type")]
            return []

        self.validator.add_rule("port_type", check_port)
        result = self.validator.validate({"port": "not_a_number"})
        self.assertFalse(result.valid)
        self.assertEqual(len(result.errors), 1)

    def test_validate_with_best_practice(self) -> None:
        def bp(cfg: dict, path: str) -> list[ValidationIssue]:
            return [ValidationIssue(path="", message="hint", severity=Severity.WARNING, rule="bp")]

        self.validator.add_best_practice("bp", bp)
        result = self.validator.validate({})
        self.assertTrue(result.valid)  # warnings don't make it invalid
        self.assertEqual(len(result.warnings), 1)

    # -- Schema validation -------------------------------------------------

    def test_schema_required_field_missing(self) -> None:
        self.validator.register_schema("app", {
            "required": ["host", "port"],
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
            },
        })
        result = self.validator.validate({"host": "localhost"}, schema_name="app")
        self.assertFalse(result.valid)
        self.assertTrue(any("port" in i.message for i in result.errors))

    def test_schema_type_mismatch(self) -> None:
        self.validator.register_schema("app", {
            "properties": {
                "port": {"type": "integer"},
            },
        })
        result = self.validator.validate({"port": "abc"}, schema_name="app")
        self.assertFalse(result.valid)

    def test_schema_valid(self) -> None:
        self.validator.register_schema("app", {
            "required": ["host"],
            "properties": {
                "host": {"type": "string"},
            },
        })
        result = self.validator.validate({"host": "localhost"}, schema_name="app")
        self.assertTrue(result.valid)

    def test_schema_not_found(self) -> None:
        result = self.validator.validate({}, schema_name="nope")
        self.assertFalse(result.valid)

    def test_list_schemas(self) -> None:
        self.validator.register_schema("a", {})
        self.validator.register_schema("b", {})
        self.assertEqual(self.validator.list_schemas(), ["a", "b"])

    # -- JSON string validation --------------------------------------------

    def test_validate_json_string_valid(self) -> None:
        result = self.validator.validate_json_string('{"host": "localhost"}')
        self.assertTrue(result.valid)

    def test_validate_json_string_invalid_json(self) -> None:
        result = self.validator.validate_json_string("not json")
        self.assertFalse(result.valid)

    def test_validate_json_string_not_object(self) -> None:
        result = self.validator.validate_json_string("[1,2,3]")
        self.assertFalse(result.valid)

    # -- Cross-reference ---------------------------------------------------

    def test_cross_validate_finds_missing_keys(self) -> None:
        configs = {
            "dev": {"host": "localhost", "port": 5432},
            "prod": {"host": "prod.db"},
        }
        issues = self.validator.cross_validate(configs)
        paths = [i.path for i in issues]
        self.assertIn("port", paths)

    def test_cross_validate_no_issues(self) -> None:
        configs = {
            "dev": {"host": "localhost"},
            "prod": {"host": "prod.db"},
        }
        issues = self.validator.cross_validate(configs)
        self.assertEqual(issues, [])

    # -- Dependency validation ---------------------------------------------

    def test_validate_dependencies_ok(self) -> None:
        config = {"ssl": True, "ssl_cert": "/path/cert"}
        deps = {"ssl": ["ssl_cert"]}
        issues = self.validator.validate_dependencies(config, deps)
        self.assertEqual(issues, [])

    def test_validate_dependencies_missing(self) -> None:
        config = {"ssl": True}
        deps = {"ssl": ["ssl_cert"]}
        issues = self.validator.validate_dependencies(config, deps)
        self.assertEqual(len(issues), 1)

    # -- With defaults (best practices) ------------------------------------

    def test_with_defaults_empty_string_warning(self) -> None:
        v = ConfigValidator.with_defaults()
        result = v.validate({"name": ""})
        self.assertTrue(any(i.rule == "no_empty_strings" for i in result.issues))

    def test_with_defaults_placeholder_secret(self) -> None:
        v = ConfigValidator.with_defaults()
        result = v.validate({"api_key": "TODO"})
        self.assertFalse(result.valid)
        self.assertTrue(any(i.rule == "no_placeholder_secrets" for i in result.issues))

    def test_with_defaults_real_secret_ok(self) -> None:
        v = ConfigValidator.with_defaults()
        result = v.validate({"api_key": "sk-real-key-123"})
        self.assertTrue(result.valid)

    # -- ValidationResult properties ---------------------------------------

    def test_result_errors_and_warnings(self) -> None:
        result = ValidationResult(
            valid=False,
            issues=[
                ValidationIssue(path="a", message="err", severity=Severity.ERROR),
                ValidationIssue(path="b", message="warn", severity=Severity.WARNING),
                ValidationIssue(path="c", message="info", severity=Severity.INFO),
            ],
            checked_rules=3,
        )
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.warnings), 1)

    # -- Type matching -----------------------------------------------------

    def test_type_matches_all_types(self) -> None:
        self.validator.register_schema("types", {
            "properties": {
                "s": {"type": "string"},
                "i": {"type": "integer"},
                "n": {"type": "number"},
                "b": {"type": "boolean"},
                "a": {"type": "array"},
                "o": {"type": "object"},
            },
        })
        result = self.validator.validate(
            {"s": "x", "i": 1, "n": 1.5, "b": True, "a": [1], "o": {"k": "v"}},
            schema_name="types",
        )
        self.assertTrue(result.valid)


if __name__ == "__main__":
    unittest.main()
