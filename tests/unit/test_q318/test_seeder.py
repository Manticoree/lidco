"""Tests for lidco.testdata.seeder (Task 1705)."""

from __future__ import annotations

import unittest

from lidco.testdata.fixtures import FixtureDef
from lidco.testdata.seeder import (
    DataSeeder,
    Environment,
    SeedEntry,
    SeedPlan,
    SeedResult,
    SeedStatus,
    ValidationError,
)


class TestSeedStatus(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(SeedStatus.PENDING.value, "pending")
        self.assertEqual(SeedStatus.APPLIED.value, "applied")
        self.assertEqual(SeedStatus.FAILED.value, "failed")
        self.assertEqual(SeedStatus.ROLLED_BACK.value, "rolled_back")


class TestEnvironment(unittest.TestCase):
    def test_values(self) -> None:
        self.assertEqual(Environment.DEVELOPMENT.value, "development")
        self.assertEqual(Environment.TESTING.value, "testing")
        self.assertEqual(Environment.STAGING.value, "staging")
        self.assertEqual(Environment.PRODUCTION.value, "production")


class TestSeedEntry(unittest.TestCase):
    def test_frozen(self) -> None:
        e = SeedEntry("f", "t")
        with self.assertRaises(AttributeError):
            e.status = SeedStatus.APPLIED  # type: ignore[misc]

    def test_defaults(self) -> None:
        e = SeedEntry("f", "t")
        self.assertEqual(e.status, SeedStatus.PENDING)
        self.assertEqual(e.record_count, 0)
        self.assertIsNone(e.error)


class TestSeedPlan(unittest.TestCase):
    def test_total_records(self) -> None:
        plan = SeedPlan(entries=(
            SeedEntry("a", "t1", record_count=5),
            SeedEntry("b", "t2", record_count=3),
        ))
        self.assertEqual(plan.total_records, 8)

    def test_tables(self) -> None:
        plan = SeedPlan(entries=(
            SeedEntry("a", "t1"),
            SeedEntry("b", "t2"),
            SeedEntry("c", "t1"),
        ))
        self.assertEqual(plan.tables, ["t1", "t2"])

    def test_defaults(self) -> None:
        plan = SeedPlan()
        self.assertEqual(plan.environment, "development")
        self.assertTrue(plan.idempotent)


class TestSeedResult(unittest.TestCase):
    def test_success(self) -> None:
        r = SeedResult(applied=(SeedEntry("a", "t", record_count=2),))
        self.assertTrue(r.success)
        self.assertEqual(r.total_applied, 2)

    def test_failure(self) -> None:
        r = SeedResult(
            failed=(SeedEntry("a", "t", status=SeedStatus.FAILED, error="boom"),),
        )
        self.assertFalse(r.success)

    def test_rolled_back(self) -> None:
        r = SeedResult(rolled_back=True)
        self.assertTrue(r.rolled_back)


class TestValidationError(unittest.TestCase):
    def test_frozen(self) -> None:
        ve = ValidationError("f", "field", "msg")
        with self.assertRaises(AttributeError):
            ve.message = "x"  # type: ignore[misc]


class TestDataSeeder(unittest.TestCase):
    def _fixture(self, name: str = "users", data: dict | None = None) -> FixtureDef:
        return FixtureDef(name=name, data=data or {"id": 1, "name": "Alice"})

    def test_add_fixture(self) -> None:
        seeder = DataSeeder().add_fixture("u", "users", self._fixture())
        self.assertEqual(seeder.fixture_names, ["u"])

    def test_environment(self) -> None:
        seeder = DataSeeder(environment="testing")
        self.assertEqual(seeder.environment, "testing")

    def test_plan(self) -> None:
        seeder = DataSeeder().add_fixture("u", "users", self._fixture())
        plan = seeder.plan()
        self.assertEqual(len(plan.entries), 1)
        self.assertEqual(plan.entries[0].fixture_name, "u")
        self.assertEqual(plan.entries[0].table, "users")

    def test_execute_success(self) -> None:
        seeder = DataSeeder().add_fixture("u", "users", self._fixture())
        result = seeder.execute()
        self.assertTrue(result.success)
        self.assertEqual(len(result.applied), 1)
        self.assertEqual(result.applied[0].status, SeedStatus.APPLIED)

    def test_execute_with_backend(self) -> None:
        calls: list[tuple[str, dict]] = []

        def backend(table: str, data: dict) -> bool:
            calls.append((table, data))
            return True

        seeder = DataSeeder(backend=backend).add_fixture("u", "users", self._fixture())
        result = seeder.execute()
        self.assertTrue(result.success)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "users")

    def test_execute_backend_rejects(self) -> None:
        def bad_backend(table: str, data: dict) -> bool:
            return False

        seeder = DataSeeder(backend=bad_backend).add_fixture("u", "users", self._fixture())
        result = seeder.execute()
        self.assertFalse(result.success)
        self.assertEqual(len(result.failed), 1)

    def test_idempotent_skip(self) -> None:
        seeder = DataSeeder(idempotent=True).add_fixture("u", "users", self._fixture())
        r1 = seeder.execute()
        r2 = seeder.execute()
        self.assertTrue(r1.success)
        self.assertTrue(r2.success)
        # Second run should still succeed (idempotent)
        self.assertEqual(seeder.applied_count, 1)

    def test_validate_empty_data(self) -> None:
        empty_fx = FixtureDef(name="empty", data={})
        seeder = DataSeeder().add_fixture("e", "t", empty_fx)
        errors = seeder.validate()
        self.assertTrue(any(e.fixture_name == "e" for e in errors))

    def test_validate_empty_table(self) -> None:
        seeder = DataSeeder().add_fixture("x", "", self._fixture())
        errors = seeder.validate()
        self.assertTrue(any(e.field == "table" for e in errors))

    def test_validate_clean(self) -> None:
        seeder = DataSeeder().add_fixture("u", "users", self._fixture())
        errors = seeder.validate()
        self.assertEqual(len(errors), 0)

    def test_rollback(self) -> None:
        seeder = DataSeeder().add_fixture("u", "users", self._fixture())
        seeder.execute()
        result = seeder.rollback()
        self.assertTrue(result.rolled_back)
        self.assertEqual(len(result.applied), 1)
        self.assertEqual(result.applied[0].status, SeedStatus.ROLLED_BACK)
        self.assertEqual(seeder.applied_count, 0)

    def test_rollback_empty(self) -> None:
        seeder = DataSeeder()
        result = seeder.rollback()
        self.assertTrue(result.rolled_back)
        self.assertEqual(len(result.applied), 0)

    def test_execute_unknown_fixture_in_plan(self) -> None:
        # Build a plan with an entry not in the seeder
        seeder = DataSeeder()
        plan = SeedPlan(entries=(SeedEntry("ghost", "t", record_count=1),))
        result = seeder.execute(plan)
        self.assertFalse(result.success)
        self.assertEqual(result.failed[0].error, "Unknown fixture: ghost")

    def test_multiple_fixtures(self) -> None:
        seeder = (
            DataSeeder()
            .add_fixture("u", "users", self._fixture("users"))
            .add_fixture("r", "roles", self._fixture("roles", {"admin": True}))
        )
        result = seeder.execute()
        self.assertTrue(result.success)
        self.assertEqual(len(result.applied), 2)


if __name__ == "__main__":
    unittest.main()
