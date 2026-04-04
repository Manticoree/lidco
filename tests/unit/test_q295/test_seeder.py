"""Tests for DataSeeder."""
from __future__ import annotations

import unittest

from lidco.database.seeder import DataSeeder, SeedColumn, SeedTable


class TestDataSeederAddTable(unittest.TestCase):
    def test_add_table_returns_seed_table(self):
        ds = DataSeeder()
        t = ds.add_table("users", [SeedColumn("id", "int")])
        self.assertIsInstance(t, SeedTable)
        self.assertEqual(t.name, "users")

    def test_add_table_immutable(self):
        ds = DataSeeder()
        cols = [SeedColumn("id", "int")]
        ds.add_table("users", cols)
        cols.append(SeedColumn("extra", "text"))
        # Internal copy should not be affected
        self.assertEqual(len(ds._tables["users"].columns), 1)


class TestDataSeederGenerate(unittest.TestCase):
    def setUp(self):
        self.ds = DataSeeder()
        self.ds.add_table("users", [
            SeedColumn("id", "int", unique=True),
            SeedColumn("name", "name"),
            SeedColumn("email", "email"),
            SeedColumn("active", "bool"),
        ])

    def test_generate_count(self):
        rows = self.ds.generate("users", 5)
        self.assertEqual(len(rows), 5)

    def test_generate_has_all_columns(self):
        rows = self.ds.generate("users", 1)
        for key in ("id", "name", "email", "active"):
            self.assertIn(key, rows[0])

    def test_generate_unknown_table_raises(self):
        with self.assertRaises(ValueError):
            self.ds.generate("unknown", 5)

    def test_unique_column_values(self):
        rows = self.ds.generate("users", 50)
        ids = [r["id"] for r in rows if r["id"] is not None]
        self.assertEqual(len(ids), len(set(ids)))

    def test_generate_types(self):
        self.ds.add_table("typed", [
            SeedColumn("i", "int"),
            SeedColumn("f", "float"),
            SeedColumn("d", "date"),
            SeedColumn("t", "text"),
        ])
        self.ds.deterministic(99)
        rows = self.ds.generate("typed", 10)
        for row in rows:
            if row["i"] is not None:
                self.assertIsInstance(row["i"], int)
            if row["f"] is not None:
                self.assertIsInstance(row["f"], float)
            if row["d"] is not None:
                self.assertIsInstance(row["d"], str)

    def test_nullable_columns(self):
        self.ds.add_table("nullable", [SeedColumn("val", "text", nullable=True)])
        self.ds.deterministic(0)
        rows = self.ds.generate("nullable", 200)
        nulls = [r for r in rows if r["val"] is None]
        # With 10% nullable chance and 200 rows, expect some nulls
        self.assertTrue(len(nulls) > 0)

    def test_email_format(self):
        self.ds.deterministic(42)
        rows = self.ds.generate("users", 10)
        for row in rows:
            if row["email"] is not None:
                self.assertIn("@", row["email"])


class TestDataSeederDeterministic(unittest.TestCase):
    def test_same_seed_same_output(self):
        ds1 = DataSeeder()
        ds1.add_table("t", [SeedColumn("v", "int")])
        ds1.deterministic(123)
        rows1 = ds1.generate("t", 10)

        ds2 = DataSeeder()
        ds2.add_table("t", [SeedColumn("v", "int")])
        ds2.deterministic(123)
        rows2 = ds2.generate("t", 10)

        self.assertEqual(rows1, rows2)

    def test_different_seed_different_output(self):
        ds1 = DataSeeder()
        ds1.add_table("t", [SeedColumn("v", "int")])
        ds1.deterministic(1)
        rows1 = ds1.generate("t", 10)

        ds2 = DataSeeder()
        ds2.add_table("t", [SeedColumn("v", "int")])
        ds2.deterministic(2)
        rows2 = ds2.generate("t", 10)

        self.assertNotEqual(rows1, rows2)


class TestDataSeederWithReferences(unittest.TestCase):
    def setUp(self):
        self.ds = DataSeeder()
        self.ds.add_table("users", [SeedColumn("id", "int", unique=True)])
        self.ds.add_table("orders", [
            SeedColumn("id", "int", unique=True),
            SeedColumn("user_id", "int", foreign_key="users.id"),
        ])

    def test_with_references_fills_fk(self):
        user_rows = self.ds.generate("users", 5)
        user_ids = {r["id"] for r in user_rows}
        order_rows = self.ds.generate("orders", 10)
        updated = self.ds.with_references("orders", "users")
        for row in updated:
            self.assertIn(row["user_id"], user_ids)

    def test_with_references_unknown_table_raises(self):
        with self.assertRaises(ValueError):
            self.ds.with_references("unknown", "users")

    def test_with_references_no_fk_data_raises(self):
        with self.assertRaises(ValueError):
            self.ds.with_references("orders", "users")


if __name__ == "__main__":
    unittest.main()
