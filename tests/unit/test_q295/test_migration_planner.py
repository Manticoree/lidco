"""Tests for MigrationPlanner2."""
from __future__ import annotations

import unittest

from lidco.database.migration_planner import MigrationPlan, MigrationPlanner2, MigrationStep, SchemaSnapshot


class TestMigrationPlanner2Plan(unittest.TestCase):
    def setUp(self):
        self.mp = MigrationPlanner2()

    def test_add_table_detected(self):
        old = SchemaSnapshot(tables={})
        new = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}}})
        plan = self.mp.plan(old, new)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].operation, "add_table")
        self.assertEqual(plan.steps[0].table, "users")

    def test_drop_table_detected(self):
        old = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}}})
        new = SchemaSnapshot(tables={})
        plan = self.mp.plan(old, new)
        self.assertEqual(plan.steps[0].operation, "drop_table")
        self.assertTrue(plan.steps[0].breaking)

    def test_add_column_detected(self):
        old = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}}})
        new = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}, "email": {"type": "TEXT"}}})
        plan = self.mp.plan(old, new)
        add_steps = [s for s in plan.steps if s.operation == "add_column"]
        self.assertEqual(len(add_steps), 1)
        self.assertEqual(add_steps[0].column, "email")

    def test_drop_column_detected(self):
        old = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}, "old_col": {"type": "TEXT"}}})
        new = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}}})
        plan = self.mp.plan(old, new)
        drop_steps = [s for s in plan.steps if s.operation == "drop_column"]
        self.assertEqual(len(drop_steps), 1)
        self.assertTrue(drop_steps[0].breaking)

    def test_alter_column_detected(self):
        old = SchemaSnapshot(tables={"users": {"name": {"type": "TEXT"}}})
        new = SchemaSnapshot(tables={"users": {"name": {"type": "VARCHAR(255)"}}})
        plan = self.mp.plan(old, new)
        alter_steps = [s for s in plan.steps if s.operation == "alter_column"]
        self.assertEqual(len(alter_steps), 1)
        self.assertTrue(alter_steps[0].breaking)

    def test_no_changes_empty_plan(self):
        schema = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}}})
        plan = self.mp.plan(schema, schema)
        self.assertEqual(len(plan.steps), 0)

    def test_add_nullable_column_not_breaking(self):
        old = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}}})
        new = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}, "bio": {"type": "TEXT", "nullable": True}}})
        plan = self.mp.plan(old, new)
        add_steps = [s for s in plan.steps if s.operation == "add_column"]
        self.assertFalse(add_steps[0].breaking)

    def test_add_non_nullable_no_default_breaking(self):
        old = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}}})
        new = SchemaSnapshot(tables={"users": {"id": {"type": "INT"}, "email": {"type": "TEXT", "nullable": False}}})
        plan = self.mp.plan(old, new)
        add_steps = [s for s in plan.steps if s.operation == "add_column"]
        self.assertTrue(add_steps[0].breaking)

    def test_plan_stored_in_history(self):
        old = SchemaSnapshot(tables={})
        new = SchemaSnapshot(tables={"t": {"id": {"type": "INT"}}})
        self.mp.plan(old, new)
        self.assertEqual(len(self.mp.history), 1)


class TestMigrationPlanner2DetectBreaking(unittest.TestCase):
    def setUp(self):
        self.mp = MigrationPlanner2()

    def test_detect_breaking(self):
        plan = MigrationPlan(steps=[
            MigrationStep("add_table", "t1"),
            MigrationStep("drop_table", "t2", breaking=True),
            MigrationStep("add_column", "t1", "col", breaking=False),
        ])
        breaking = self.mp.detect_breaking(plan)
        self.assertEqual(len(breaking), 1)
        self.assertEqual(breaking[0].table, "t2")

    def test_no_breaking(self):
        plan = MigrationPlan(steps=[MigrationStep("add_table", "t1")])
        self.assertEqual(len(self.mp.detect_breaking(plan)), 0)


class TestMigrationPlanner2Rollback(unittest.TestCase):
    def setUp(self):
        self.mp = MigrationPlanner2()

    def test_rollback_add_table(self):
        plan = MigrationPlan(steps=[MigrationStep("add_table", "users")])
        rb = self.mp.generate_rollback(plan)
        self.assertIn("DROP TABLE", rb)
        self.assertIn("users", rb)

    def test_rollback_drop_table(self):
        plan = MigrationPlan(steps=[MigrationStep("drop_table", "users", breaking=True)])
        rb = self.mp.generate_rollback(plan)
        self.assertIn("CREATE TABLE", rb)

    def test_rollback_add_column(self):
        plan = MigrationPlan(steps=[MigrationStep("add_column", "users", "email")])
        rb = self.mp.generate_rollback(plan)
        self.assertIn("DROP COLUMN", rb)
        self.assertIn("email", rb)

    def test_rollback_alter_column(self):
        plan = MigrationPlan(steps=[MigrationStep(
            "alter_column", "users", "name",
            details={"old": {"type": "TEXT"}, "new": {"type": "VARCHAR"}},
            breaking=True,
        )])
        rb = self.mp.generate_rollback(plan)
        self.assertIn("ALTER", rb)
        self.assertIn("TEXT", rb)


class TestMigrationPlanner2IsSafe(unittest.TestCase):
    def test_safe_plan(self):
        mp = MigrationPlanner2()
        plan = MigrationPlan(steps=[MigrationStep("add_table", "t1")])
        self.assertTrue(mp.is_safe(plan))

    def test_unsafe_plan(self):
        mp = MigrationPlanner2()
        plan = MigrationPlan(steps=[MigrationStep("drop_table", "t1", breaking=True)])
        self.assertFalse(mp.is_safe(plan))


if __name__ == "__main__":
    unittest.main()
