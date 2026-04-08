"""Tests for ConfigSchemaValidator (Q345)."""
from __future__ import annotations

import unittest


def _validator():
    from lidco.stability.config_schema import ConfigSchemaValidator
    return ConfigSchemaValidator()


def _schema(*fields):
    """Build a schema dict from field dicts."""
    return {"fields": list(fields)}


def _field(name, ftype="str", required=False, **kwargs):
    f = {"name": name, "type": ftype, "required": required}
    f.update(kwargs)
    return f


class TestValidateDefaults(unittest.TestCase):
    def test_field_with_default_reports_has_default(self):
        schema = _schema(_field("host", "str", required=True, default="localhost"))
        results = _validator().validate_defaults(schema)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["has_default"])

    def test_required_field_without_default_flagged(self):
        schema = _schema(_field("port", "int", required=True))
        results = _validator().validate_defaults(schema)
        self.assertFalse(results[0]["has_default"])
        self.assertIn("Required", results[0]["suggestion"])

    def test_optional_field_without_default_gets_suggestion(self):
        schema = _schema(_field("debug", "bool", required=False))
        results = _validator().validate_defaults(schema)
        self.assertFalse(results[0]["has_default"])
        self.assertIn("Optional", results[0]["suggestion"])

    def test_empty_schema_returns_empty_list(self):
        results = _validator().validate_defaults({"fields": []})
        self.assertEqual(results, [])


class TestRejectUnknownKeys(unittest.TestCase):
    def test_known_keys_not_flagged(self):
        schema = _schema(_field("host"), _field("port"))
        config = {"host": "localhost", "port": 8080}
        unknown = _validator().reject_unknown_keys(config, schema)
        self.assertEqual(unknown, [])

    def test_unknown_key_flagged(self):
        schema = _schema(_field("host"))
        config = {"host": "localhost", "extra_key": "value"}
        unknown = _validator().reject_unknown_keys(config, schema)
        self.assertIn("extra_key", unknown)

    def test_multiple_unknown_keys_all_returned(self):
        schema = _schema(_field("a"))
        config = {"a": 1, "b": 2, "c": 3}
        unknown = _validator().reject_unknown_keys(config, schema)
        self.assertIn("b", unknown)
        self.assertIn("c", unknown)

    def test_empty_config_returns_empty(self):
        schema = _schema(_field("host"))
        unknown = _validator().reject_unknown_keys({}, schema)
        self.assertEqual(unknown, [])


class TestCheckTypeCoercion(unittest.TestCase):
    def test_matching_types_no_issue(self):
        schema = _schema(_field("port", "int"))
        config = {"port": 8080}
        results = _validator().check_type_coercion(config, schema)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["coercible"])

    def test_string_port_is_coercible_to_int(self):
        schema = _schema(_field("port", "int"))
        config = {"port": "8080"}
        results = _validator().check_type_coercion(config, schema)
        self.assertTrue(results[0]["coercible"])

    def test_non_numeric_string_not_coercible_to_int(self):
        schema = _schema(_field("port", "int"))
        config = {"port": "not_a_number"}
        results = _validator().check_type_coercion(config, schema)
        self.assertFalse(results[0]["coercible"])

    def test_unknown_config_key_not_reported(self):
        schema = _schema(_field("host", "str"))
        config = {"host": "localhost", "extra": 99}
        results = _validator().check_type_coercion(config, schema)
        keys_reported = [r["field"] for r in results]
        self.assertNotIn("extra", keys_reported)

    def test_result_contains_expected_and_actual_types(self):
        schema = _schema(_field("flag", "bool"))
        config = {"flag": "true"}
        results = _validator().check_type_coercion(config, schema)
        self.assertEqual(results[0]["expected_type"], "bool")
        self.assertEqual(results[0]["actual_type"], "str")


class TestGenerateSchema(unittest.TestCase):
    def test_extracts_dataclass_fields(self):
        code = (
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Config:\n"
            "    host: str = 'localhost'\n"
            "    port: int = 8080\n"
            "    debug: bool = False\n"
        )
        schema = _validator().generate_schema(code)
        names = [f["name"] for f in schema["fields"]]
        self.assertIn("host", names)
        self.assertIn("port", names)
        self.assertIn("debug", names)

    def test_field_without_default_is_required(self):
        code = (
            "from dataclasses import dataclass\n"
            "@dataclass\n"
            "class Config:\n"
            "    name: str\n"
        )
        schema = _validator().generate_schema(code)
        self.assertEqual(len(schema["fields"]), 1)
        self.assertTrue(schema["fields"][0]["required"])

    def test_invalid_syntax_returns_empty(self):
        schema = _validator().generate_schema("class Broken(:")
        self.assertEqual(schema["fields"], [])

    def test_non_dataclass_not_extracted(self):
        code = "class Plain:\n    x: int = 1\n"
        schema = _validator().generate_schema(code)
        self.assertEqual(schema["fields"], [])


if __name__ == "__main__":
    unittest.main()
