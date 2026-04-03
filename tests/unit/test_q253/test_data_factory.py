"""Tests for TestDataFactory (Q253)."""
from __future__ import annotations

import unittest

from lidco.testgen.data_factory import Schema, TestDataFactory


class TestSchema(unittest.TestCase):
    def test_frozen(self):
        s = Schema(fields=[{"name": "x", "type": "int"}])
        with self.assertRaises(AttributeError):
            s.fields = []  # type: ignore[misc]

    def test_defaults(self):
        s = Schema()
        self.assertEqual(s.fields, [])


class TestRandomString(unittest.TestCase):
    def setUp(self):
        self.factory = TestDataFactory()

    def test_default_length(self):
        s = self.factory.random_string()
        self.assertEqual(len(s), 10)

    def test_custom_length(self):
        s = self.factory.random_string(length=20)
        self.assertEqual(len(s), 20)

    def test_seed_deterministic(self):
        a = self.factory.random_string(seed=42)
        b = self.factory.random_string(seed=42)
        self.assertEqual(a, b)

    def test_all_alpha(self):
        s = self.factory.random_string(length=50, seed=1)
        self.assertTrue(s.isalpha())


class TestRandomInt(unittest.TestCase):
    def setUp(self):
        self.factory = TestDataFactory()

    def test_default_range(self):
        val = self.factory.random_int()
        self.assertGreaterEqual(val, 0)
        self.assertLessEqual(val, 1000)

    def test_custom_range(self):
        val = self.factory.random_int(min_val=10, max_val=20)
        self.assertGreaterEqual(val, 10)
        self.assertLessEqual(val, 20)

    def test_seed_deterministic(self):
        a = self.factory.random_int(seed=42)
        b = self.factory.random_int(seed=42)
        self.assertEqual(a, b)

    def test_single_value(self):
        val = self.factory.random_int(min_val=5, max_val=5)
        self.assertEqual(val, 5)


class TestRandomEmail(unittest.TestCase):
    def setUp(self):
        self.factory = TestDataFactory()

    def test_format(self):
        email = self.factory.random_email()
        self.assertIn("@", email)
        self.assertTrue(email.endswith(".com"))

    def test_seed_deterministic(self):
        a = self.factory.random_email(seed=42)
        b = self.factory.random_email(seed=42)
        self.assertEqual(a, b)


class TestGenerate(unittest.TestCase):
    def setUp(self):
        self.factory = TestDataFactory()

    def test_single_row(self):
        schema = Schema(fields=[
            {"name": "name", "type": "str"},
            {"name": "age", "type": "int", "min": 0, "max": 100},
        ])
        rows = self.factory.generate(schema, count=1, seed=42)
        self.assertEqual(len(rows), 1)
        self.assertIn("name", rows[0])
        self.assertIn("age", rows[0])
        self.assertIsInstance(rows[0]["name"], str)
        self.assertIsInstance(rows[0]["age"], int)

    def test_multiple_rows(self):
        schema = Schema(fields=[{"name": "x", "type": "int"}])
        rows = self.factory.generate(schema, count=5, seed=42)
        self.assertEqual(len(rows), 5)

    def test_seed_deterministic(self):
        schema = Schema(fields=[
            {"name": "val", "type": "int", "min": 0, "max": 999},
        ])
        a = self.factory.generate(schema, count=3, seed=99)
        b = self.factory.generate(schema, count=3, seed=99)
        self.assertEqual(a, b)

    def test_float_type(self):
        schema = Schema(fields=[{"name": "score", "type": "float", "min": 0.0, "max": 1.0}])
        rows = self.factory.generate(schema, count=1, seed=42)
        self.assertIsInstance(rows[0]["score"], float)
        self.assertGreaterEqual(rows[0]["score"], 0.0)
        self.assertLessEqual(rows[0]["score"], 1.0)

    def test_bool_type(self):
        schema = Schema(fields=[{"name": "active", "type": "bool"}])
        rows = self.factory.generate(schema, count=1, seed=42)
        self.assertIsInstance(rows[0]["active"], bool)

    def test_choices(self):
        schema = Schema(fields=[{"name": "color", "type": "str", "choices": ["red", "blue"]}])
        rows = self.factory.generate(schema, count=10, seed=42)
        for row in rows:
            self.assertIn(row["color"], ["red", "blue"])

    def test_email_type(self):
        schema = Schema(fields=[{"name": "email", "type": "email"}])
        rows = self.factory.generate(schema, count=1, seed=42)
        self.assertIn("@", rows[0]["email"])

    def test_empty_schema(self):
        schema = Schema()
        rows = self.factory.generate(schema, count=3)
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row, {})

    def test_int_respects_bounds(self):
        schema = Schema(fields=[{"name": "x", "type": "int", "min": 50, "max": 60}])
        rows = self.factory.generate(schema, count=20, seed=42)
        for row in rows:
            self.assertGreaterEqual(row["x"], 50)
            self.assertLessEqual(row["x"], 60)


if __name__ == "__main__":
    unittest.main()
