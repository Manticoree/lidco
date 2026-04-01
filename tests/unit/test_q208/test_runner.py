"""Tests for lidco.migrations.runner — MigrationRunner."""

from __future__ import annotations

import unittest

from lidco.migrations.runner import (
    Migration,
    MigrationError,
    MigrationResult,
    MigrationRunner,
    MigrationStatus,
)


class TestMigrationStatus(unittest.TestCase):
    def test_enum_values(self) -> None:
        assert MigrationStatus.PENDING == "pending"
        assert MigrationStatus.APPLIED == "applied"
        assert MigrationStatus.ROLLED_BACK == "rolled_back"
        assert MigrationStatus.FAILED == "failed"


class TestMigrationRunner(unittest.TestCase):
    def _make_runner(self) -> MigrationRunner:
        runner = MigrationRunner()
        runner.add(Migration(version="001", name="create_users", up_sql="CREATE TABLE users;", down_sql="DROP TABLE users;"))
        runner.add(Migration(version="002", name="create_posts", up_sql="CREATE TABLE posts;", down_sql="DROP TABLE posts;"))
        runner.add(Migration(version="003", name="add_index", up_sql="CREATE INDEX idx;", down_sql="DROP INDEX idx;"))
        return runner

    def test_add_and_get_status(self) -> None:
        runner = self._make_runner()
        statuses = runner.get_status()
        assert len(statuses) == 3
        assert all(m.status == MigrationStatus.PENDING for m in statuses)

    def test_run_up_all(self) -> None:
        runner = self._make_runner()
        results = runner.run_up()
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.direction == "up" for r in results)
        assert runner.pending() == []

    def test_run_up_single(self) -> None:
        runner = self._make_runner()
        results = runner.run_up("002")
        assert len(results) == 1
        assert results[0].version == "002"
        assert results[0].success is True
        # Only 002 applied
        pending = runner.pending()
        assert len(pending) == 2

    def test_run_up_not_found(self) -> None:
        runner = self._make_runner()
        with self.assertRaises(MigrationError):
            runner.run_up("999")

    def test_run_down(self) -> None:
        runner = self._make_runner()
        runner.run_up()
        result = runner.run_down("002")
        assert result.success is True
        assert result.direction == "down"
        m = [s for s in runner.get_status() if s.version == "002"][0]
        assert m.status == MigrationStatus.ROLLED_BACK

    def test_run_down_not_found(self) -> None:
        runner = self._make_runner()
        with self.assertRaises(MigrationError):
            runner.run_down("999")

    def test_dry_run_all(self) -> None:
        runner = self._make_runner()
        stmts = runner.dry_run()
        assert len(stmts) == 3
        assert "CREATE TABLE users;" in stmts

    def test_dry_run_single(self) -> None:
        runner = self._make_runner()
        stmts = runner.dry_run("002")
        assert len(stmts) == 1
        assert stmts[0] == "CREATE TABLE posts;"

    def test_pending(self) -> None:
        runner = self._make_runner()
        assert len(runner.pending()) == 3
        runner.run_up("001")
        assert len(runner.pending()) == 2

    def test_history(self) -> None:
        runner = self._make_runner()
        assert runner.history() == []
        runner.run_up()
        assert len(runner.history()) == 3

    def test_latest_version(self) -> None:
        runner = self._make_runner()
        assert runner.latest_version() is None
        runner.run_up()
        assert runner.latest_version() == "003"

    def test_rollback_all(self) -> None:
        runner = self._make_runner()
        runner.run_up()
        results = runner.rollback_all()
        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.direction == "down" for r in results)
        # Reversed order
        assert results[0].version == "003"
        assert results[1].version == "002"
        assert results[2].version == "001"


if __name__ == "__main__":
    unittest.main()
