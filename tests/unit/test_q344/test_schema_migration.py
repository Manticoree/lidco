"""Tests for SchemaMigrationValidator (Q344)."""
from __future__ import annotations

import unittest


def _validator():
    from lidco.stability.schema_migration import SchemaMigrationValidator
    return SchemaMigrationValidator()


def _schema(*tables):
    """Build a schema dict from (table_name, [col_dict, ...]) pairs."""
    return {"tables": {name: cols for name, cols in tables}}


def _col(name, ctype="TEXT", nullable=True):
    return {"name": name, "type": ctype, "nullable": nullable}


class TestValidateUpgradeCompatible(unittest.TestCase):
    def test_identical_schemas_are_compatible(self):
        schema = _schema(("users", [_col("id", "INT", False), _col("email")]))
        result = _validator().validate_upgrade(schema, schema)
        self.assertTrue(result["compatible"])
        self.assertEqual(result["breaking_changes"], [])
        self.assertEqual(result["additions"], [])

    def test_adding_nullable_column_is_compatible(self):
        old = _schema(("users", [_col("id", "INT", False)]))
        new = _schema(("users", [_col("id", "INT", False), _col("name", "TEXT", True)]))
        result = _validator().validate_upgrade(old, new)
        self.assertTrue(result["compatible"])
        self.assertEqual(len(result["additions"]), 1)
        self.assertIn("name", result["additions"][0])

    def test_adding_not_null_column_is_breaking(self):
        old = _schema(("users", [_col("id", "INT", False)]))
        new = _schema(("users", [_col("id", "INT", False), _col("score", "INT", False)]))
        result = _validator().validate_upgrade(old, new)
        self.assertFalse(result["compatible"])
        self.assertTrue(any("score" in bc for bc in result["breaking_changes"]))

    def test_dropping_column_is_breaking(self):
        old = _schema(("users", [_col("id", "INT", False), _col("email")]))
        new = _schema(("users", [_col("id", "INT", False)]))
        result = _validator().validate_upgrade(old, new)
        self.assertFalse(result["compatible"])
        self.assertTrue(any("email" in bc for bc in result["breaking_changes"]))

    def test_dropping_table_is_breaking(self):
        old = _schema(("users", [_col("id")]), ("orders", [_col("id")]))
        new = _schema(("users", [_col("id")]))
        result = _validator().validate_upgrade(old, new)
        self.assertFalse(result["compatible"])
        self.assertTrue(any("orders" in bc for bc in result["breaking_changes"]))

    def test_new_table_is_addition(self):
        old = _schema(("users", [_col("id")]))
        new = _schema(("users", [_col("id")]), ("orders", [_col("id")]))
        result = _validator().validate_upgrade(old, new)
        self.assertTrue(result["compatible"])
        self.assertTrue(any("orders" in a for a in result["additions"]))

    def test_safe_type_widening_produces_warning_not_breaking(self):
        old = _schema(("users", [_col("id", "INT", False)]))
        new = _schema(("users", [_col("id", "BIGINT", False)]))
        result = _validator().validate_upgrade(old, new)
        self.assertTrue(result["compatible"])
        self.assertTrue(len(result["warnings"]) > 0)

    def test_unsafe_type_change_is_breaking(self):
        old = _schema(("users", [_col("value", "TEXT")]))
        new = _schema(("users", [_col("value", "INT")]))
        result = _validator().validate_upgrade(old, new)
        self.assertFalse(result["compatible"])


class TestCheckBackwardCompat(unittest.TestCase):
    def test_compatible_schemas_return_no_issues(self):
        schema = _schema(("users", [_col("id", "INT", False)]))
        issues = _validator().check_backward_compat(schema, schema)
        self.assertEqual(issues, [])

    def test_dropped_table_is_critical(self):
        old = _schema(("users", [_col("id")]), ("logs", [_col("id")]))
        new = _schema(("users", [_col("id")]))
        issues = _validator().check_backward_compat(old, new)
        critical = [i for i in issues if i["severity"] == "critical"]
        self.assertTrue(any(i["table"] == "logs" for i in critical))

    def test_dropped_column_is_critical(self):
        old = _schema(("users", [_col("id"), _col("email")]))
        new = _schema(("users", [_col("id")]))
        issues = _validator().check_backward_compat(old, new)
        self.assertTrue(any(i["column"] == "email" and i["severity"] == "critical" for i in issues))

    def test_nullable_to_not_null_is_critical(self):
        old = _schema(("users", [_col("email", "TEXT", True)]))
        new = _schema(("users", [_col("email", "TEXT", False)]))
        issues = _validator().check_backward_compat(old, new)
        self.assertTrue(any(i["severity"] == "critical" for i in issues))


class TestVerifyDataPreservation(unittest.TestCase):
    def test_no_risks_for_identical_schema(self):
        schema = _schema(("users", [_col("id", "INT", False)]))
        risks = _validator().verify_data_preservation(schema, schema)
        self.assertEqual(risks, [])

    def test_dropped_column_is_risk(self):
        old = _schema(("users", [_col("id"), _col("email")]))
        new = _schema(("users", [_col("id")]))
        risks = _validator().verify_data_preservation(old, new)
        self.assertTrue(any(r["column"] == "email" for r in risks))

    def test_dropped_table_is_risk(self):
        old = _schema(("users", [_col("id")]), ("logs", [_col("id")]))
        new = _schema(("users", [_col("id")]))
        risks = _validator().verify_data_preservation(old, new)
        self.assertTrue(any(r["table"] == "logs" for r in risks))


class TestGenerateRollback(unittest.TestCase):
    def test_identical_schemas_no_rollback(self):
        schema = _schema(("users", [_col("id", "INT", False)]))
        stmts = _validator().generate_rollback(schema, schema)
        self.assertEqual(stmts, [])

    def test_new_table_produces_drop_statement(self):
        old = _schema(("users", [_col("id")]))
        new = _schema(("users", [_col("id")]), ("orders", [_col("id")]))
        stmts = _validator().generate_rollback(old, new)
        self.assertTrue(any("DROP TABLE" in s and "orders" in s for s in stmts))

    def test_added_column_produces_drop_column(self):
        old = _schema(("users", [_col("id")]))
        new = _schema(("users", [_col("id"), _col("email")]))
        stmts = _validator().generate_rollback(old, new)
        self.assertTrue(any("DROP COLUMN" in s and "email" in s for s in stmts))

    def test_dropped_table_produces_create_statement(self):
        old = _schema(("users", [_col("id")]), ("logs", [_col("id")]))
        new = _schema(("users", [_col("id")]))
        stmts = _validator().generate_rollback(old, new)
        self.assertTrue(any("CREATE TABLE" in s and "logs" in s for s in stmts))
