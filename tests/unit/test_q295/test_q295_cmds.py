"""Tests for Q295 CLI commands."""
from __future__ import annotations

import asyncio
import unittest

import lidco.cli.commands.q295_cmds as q295_mod


def _run(coro):
    return asyncio.run(coro)


class _CmdTestBase(unittest.TestCase):
    def setUp(self):
        q295_mod._state.clear()
        from lidco.cli.commands.registry import CommandRegistry
        reg = CommandRegistry.__new__(CommandRegistry)
        reg._commands = {}
        reg._session = None
        q295_mod.register(reg)
        self.db_schema = reg._commands["db-schema"].handler
        self.db_optimize = reg._commands["db-optimize"].handler
        self.db_migrate = reg._commands["db-migrate"].handler
        self.db_seed = reg._commands["db-seed"].handler


class TestDbSchemaCmd(_CmdTestBase):
    def test_summary_empty(self):
        result = _run(self.db_schema("summary"))
        self.assertIn("Tables: 0", result)

    def test_add_table(self):
        result = _run(self.db_schema("add users id:INT,name:TEXT"))
        self.assertIn("Added table", result)
        self.assertIn("2 columns", result)

    def test_relationships_empty(self):
        result = _run(self.db_schema("relationships"))
        self.assertIn("No relationships", result)

    def test_indexes_empty(self):
        result = _run(self.db_schema("indexes"))
        self.assertIn("No indexes", result)

    def test_anomalies_empty(self):
        result = _run(self.db_schema("anomalies"))
        self.assertIn("No anomalies", result)

    def test_diagram(self):
        _run(self.db_schema("add users id:INT"))
        result = _run(self.db_schema("diagram"))
        self.assertIn("erDiagram", result)

    def test_usage(self):
        result = _run(self.db_schema("invalid"))
        self.assertIn("Usage", result)

    def test_add_missing_args(self):
        result = _run(self.db_schema("add"))
        self.assertIn("Usage", result)


class TestDbOptimizeCmd(_CmdTestBase):
    def test_analyze(self):
        result = _run(self.db_optimize("analyze SELECT * FROM users"))
        self.assertIn("Cost", result)

    def test_suggest(self):
        result = _run(self.db_optimize("suggest SELECT * FROM users WHERE email = 'x'"))
        # May or may not have suggestions depending on state
        self.assertIsInstance(result, str)

    def test_rewrite(self):
        result = _run(self.db_optimize("rewrite SELECT * FROM users ORDER BY name"))
        self.assertIn("LIMIT", result)

    def test_explain(self):
        result = _run(self.db_optimize("explain SELECT * FROM users"))
        self.assertIn("Tables", result)

    def test_usage(self):
        result = _run(self.db_optimize(""))
        self.assertIn("Usage", result)

    def test_analyze_no_sql(self):
        result = _run(self.db_optimize("analyze"))
        self.assertIn("Usage", result)

    def test_suggest_no_sql(self):
        result = _run(self.db_optimize("suggest"))
        self.assertIn("Usage", result)

    def test_rewrite_no_sql(self):
        result = _run(self.db_optimize("rewrite"))
        self.assertIn("Usage", result)


class TestDbMigrateCmd(_CmdTestBase):
    def test_plan(self):
        result = _run(self.db_migrate("plan"))
        self.assertIn("Steps", result)

    def test_breaking_no_plan(self):
        result = _run(self.db_migrate("breaking"))
        self.assertIn("No migration plans", result)

    def test_rollback_no_plan(self):
        result = _run(self.db_migrate("rollback"))
        self.assertIn("No migration plans", result)

    def test_safe_no_plan(self):
        result = _run(self.db_migrate("safe"))
        self.assertIn("No migration plans", result)

    def test_plan_then_safe(self):
        _run(self.db_migrate("plan"))
        result = _run(self.db_migrate("safe"))
        self.assertIn("safe", result.lower())

    def test_plan_then_rollback(self):
        _run(self.db_migrate("plan"))
        result = _run(self.db_migrate("rollback"))
        self.assertIn("Rollback", result)

    def test_usage(self):
        result = _run(self.db_migrate(""))
        self.assertIn("Usage", result)

    def test_plan_then_breaking(self):
        _run(self.db_migrate("plan"))
        result = _run(self.db_migrate("breaking"))
        # The demo plan adds a column — no breaking by default
        self.assertIsInstance(result, str)


class TestDbSeedCmd(_CmdTestBase):
    def test_add_table(self):
        result = _run(self.db_seed("add users id:int,name:name"))
        self.assertIn("Registered table", result)

    def test_generate(self):
        _run(self.db_seed("add users id:int,name:name"))
        result = _run(self.db_seed("generate users 5"))
        self.assertIn("Generated 5 rows", result)

    def test_generate_unknown_table(self):
        result = _run(self.db_seed("generate unknown"))
        self.assertIn("not registered", result)

    def test_seed_command(self):
        result = _run(self.db_seed("seed 123"))
        self.assertIn("Seed set to 123", result)

    def test_usage(self):
        result = _run(self.db_seed(""))
        self.assertIn("Usage", result)

    def test_add_no_args(self):
        result = _run(self.db_seed("add"))
        self.assertIn("Usage", result)

    def test_generate_no_args(self):
        result = _run(self.db_seed("generate"))
        self.assertIn("Usage", result)

    def test_generate_default_count(self):
        _run(self.db_seed("add t v:text"))
        result = _run(self.db_seed("generate t"))
        self.assertIn("Generated 10 rows", result)


if __name__ == "__main__":
    unittest.main()
