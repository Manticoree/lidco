"""Tests for SchemaAnalyzer."""
from __future__ import annotations

import unittest

from lidco.database.schema import Anomaly, Column, Index, Relationship, SchemaAnalyzer, Table


class TestSchemaAnalyzerAddTable(unittest.TestCase):
    def setUp(self):
        self.sa = SchemaAnalyzer()

    def test_add_table_returns_table(self):
        cols = [Column("id", "INT", primary_key=True)]
        t = self.sa.add_table("users", cols)
        self.assertIsInstance(t, Table)
        self.assertEqual(t.name, "users")
        self.assertEqual(len(t.columns), 1)

    def test_tables_property(self):
        self.sa.add_table("a", [Column("id", "INT")])
        self.sa.add_table("b", [Column("id", "INT")])
        self.assertEqual(set(self.sa.tables.keys()), {"a", "b"})

    def test_add_table_immutable(self):
        cols = [Column("id", "INT")]
        self.sa.add_table("x", cols)
        cols.append(Column("extra", "TEXT"))
        self.assertEqual(len(self.sa.tables["x"].columns), 1)


class TestSchemaAnalyzerRelationships(unittest.TestCase):
    def setUp(self):
        self.sa = SchemaAnalyzer()
        self.sa.add_table("users", [Column("id", "INT", primary_key=True)])
        self.sa.add_table("orders", [
            Column("id", "INT", primary_key=True),
            Column("user_id", "INT", foreign_key="users.id"),
        ])

    def test_detects_fk_relationship(self):
        rels = self.sa.relationships()
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0].source_table, "orders")
        self.assertEqual(rels[0].target_table, "users")
        self.assertEqual(rels[0].type, "many-to-one")

    def test_one_to_one_when_unique(self):
        sa = SchemaAnalyzer()
        sa.add_table("users", [Column("id", "INT", primary_key=True)])
        sa.add_table("profiles", [
            Column("id", "INT", primary_key=True),
            Column("user_id", "INT", foreign_key="users.id", unique=True),
        ])
        rels = sa.relationships()
        self.assertEqual(rels[0].type, "one-to-one")

    def test_no_relationships_without_fk(self):
        sa = SchemaAnalyzer()
        sa.add_table("standalone", [Column("id", "INT", primary_key=True)])
        self.assertEqual(sa.relationships(), [])


class TestSchemaAnalyzerIndexes(unittest.TestCase):
    def setUp(self):
        self.sa = SchemaAnalyzer()
        self.sa.add_table("users", [
            Column("id", "INT", primary_key=True),
            Column("email", "TEXT", unique=True),
        ])
        self.sa.add_table("orders", [
            Column("id", "INT", primary_key=True),
            Column("user_id", "INT", foreign_key="users.id"),
        ])

    def test_pk_index(self):
        idxs = self.sa.indexes()
        pk_idxs = [i for i in idxs if i.name.startswith("pk_")]
        self.assertTrue(len(pk_idxs) >= 2)

    def test_fk_index(self):
        idxs = self.sa.indexes()
        fk_idxs = [i for i in idxs if i.name == "idx_orders_user_id"]
        self.assertEqual(len(fk_idxs), 1)
        self.assertFalse(fk_idxs[0].unique)

    def test_unique_index(self):
        idxs = self.sa.indexes()
        uq = [i for i in idxs if i.name == "uq_users_email"]
        self.assertEqual(len(uq), 1)
        self.assertTrue(uq[0].unique)


class TestSchemaAnalyzerAnomalies(unittest.TestCase):
    def test_no_pk_warning(self):
        sa = SchemaAnalyzer()
        sa.add_table("nopk", [Column("name", "TEXT")])
        anoms = sa.anomalies()
        self.assertTrue(any("no primary key" in a.message for a in anoms))

    def test_nullable_fk_warning(self):
        sa = SchemaAnalyzer()
        sa.add_table("users", [Column("id", "INT", primary_key=True)])
        sa.add_table("orders", [
            Column("id", "INT", primary_key=True),
            Column("user_id", "INT", foreign_key="users.id", nullable=True),
        ])
        anoms = sa.anomalies()
        self.assertTrue(any("nullable" in a.message for a in anoms))

    def test_orphan_fk_error(self):
        sa = SchemaAnalyzer()
        sa.add_table("orders", [
            Column("id", "INT", primary_key=True),
            Column("user_id", "INT", foreign_key="ghosts.id", nullable=False),
        ])
        anoms = sa.anomalies()
        self.assertTrue(any("unknown table" in a.message for a in anoms))

    def test_wide_table_info(self):
        sa = SchemaAnalyzer()
        cols = [Column(f"col{i}", "TEXT") for i in range(25)]
        cols[0] = Column("id", "INT", primary_key=True)
        sa.add_table("wide", cols)
        anoms = sa.anomalies()
        self.assertTrue(any("normalization" in a.message for a in anoms))

    def test_no_anomalies_clean_schema(self):
        sa = SchemaAnalyzer()
        sa.add_table("clean", [Column("id", "INT", primary_key=True), Column("name", "TEXT")])
        anoms = sa.anomalies()
        self.assertEqual(len(anoms), 0)


class TestSchemaAnalyzerERDiagram(unittest.TestCase):
    def test_diagram_starts_with_er(self):
        sa = SchemaAnalyzer()
        sa.add_table("users", [Column("id", "INT", primary_key=True)])
        diagram = sa.er_diagram()
        self.assertTrue(diagram.startswith("erDiagram"))

    def test_diagram_contains_table_name(self):
        sa = SchemaAnalyzer()
        sa.add_table("orders", [Column("id", "INT", primary_key=True)])
        diagram = sa.er_diagram()
        self.assertIn("orders", diagram)

    def test_diagram_contains_relationship(self):
        sa = SchemaAnalyzer()
        sa.add_table("users", [Column("id", "INT", primary_key=True)])
        sa.add_table("orders", [
            Column("id", "INT", primary_key=True),
            Column("user_id", "INT", foreign_key="users.id", nullable=False),
        ])
        diagram = sa.er_diagram()
        self.assertIn("users", diagram)
        self.assertIn("orders", diagram)


class TestSchemaAnalyzerSummary(unittest.TestCase):
    def test_summary_keys(self):
        sa = SchemaAnalyzer()
        sa.add_table("t", [Column("id", "INT", primary_key=True)])
        s = sa.summary()
        self.assertIn("table_count", s)
        self.assertIn("relationship_count", s)
        self.assertIn("index_count", s)
        self.assertIn("anomaly_count", s)
        self.assertEqual(s["table_count"], 1)

    def test_summary_counts_correct(self):
        sa = SchemaAnalyzer()
        sa.add_table("users", [Column("id", "INT", primary_key=True)])
        sa.add_table("orders", [
            Column("id", "INT", primary_key=True),
            Column("user_id", "INT", foreign_key="users.id", nullable=False),
        ])
        s = sa.summary()
        self.assertEqual(s["table_count"], 2)
        self.assertEqual(s["relationship_count"], 1)


if __name__ == "__main__":
    unittest.main()
