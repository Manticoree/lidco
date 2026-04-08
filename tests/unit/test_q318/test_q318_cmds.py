"""Tests for lidco.cli.commands.q318_cmds (Task 1706)."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest import mock


class _FakeRegistry:
    """Minimal stub matching the register_async interface."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler: object) -> None:
        self.commands[name] = (desc, handler)


class TestQ318Commands(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q318_cmds import register_q318_commands

        self.registry = _FakeRegistry()
        register_q318_commands(self.registry)

    def _handler(self, name: str):
        return self.registry.commands[name][1]

    # -- registration -------------------------------------------------------

    def test_all_commands_registered(self) -> None:
        expected = {"test-data", "test-fixtures", "mask-data", "seed-data"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    # -- /test-data ----------------------------------------------------------

    def test_test_data_no_args(self) -> None:
        result = asyncio.run(self._handler("test-data")(""))
        self.assertIn("Usage", result)

    def test_test_data_user_schema(self) -> None:
        result = asyncio.run(self._handler("test-data")("user --count 3 --seed 7"))
        self.assertIn("Generated 3 user", result)
        self.assertIn("seed=7", result)

    def test_test_data_product_schema(self) -> None:
        result = asyncio.run(self._handler("test-data")("product --count 2"))
        self.assertIn("Generated 2 product", result)

    def test_test_data_unknown_schema(self) -> None:
        result = asyncio.run(self._handler("test-data")("nope"))
        self.assertIn("Unknown schema", result)

    # -- /test-fixtures ------------------------------------------------------

    def test_test_fixtures_no_args(self) -> None:
        result = asyncio.run(self._handler("test-fixtures")(""))
        self.assertIn("Usage", result)

    def test_test_fixtures_list_empty(self) -> None:
        result = asyncio.run(self._handler("test-fixtures")("--list"))
        self.assertIn("No fixtures registered", result)

    def test_test_fixtures_load_file(self) -> None:
        data = {"fixtures": [{"name": "t1", "scope": "test", "data": {"a": 1}}]}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            path = f.name
        try:
            result = asyncio.run(self._handler("test-fixtures")(f'--file "{path}"'))
            self.assertIn("Loaded 1 fixture", result)
            self.assertIn("t1", result)
        finally:
            os.unlink(path)

    def test_test_fixtures_load_bad_file(self) -> None:
        result = asyncio.run(self._handler("test-fixtures")("--file /no/such/file.json"))
        self.assertIn("Error loading fixtures", result)

    # -- /mask-data ----------------------------------------------------------

    def test_mask_data_no_args(self) -> None:
        result = asyncio.run(self._handler("mask-data")(""))
        self.assertIn("Usage", result)

    def test_mask_data_with_email(self) -> None:
        result = asyncio.run(self._handler("mask-data")("email is user@test.com"))
        self.assertIn("Masked", result)
        self.assertNotIn("user@test.com", result)
        self.assertIn("email", result.lower())

    def test_mask_data_no_pii(self) -> None:
        result = asyncio.run(self._handler("mask-data")("just plain text"))
        self.assertIn("No PII detected", result)

    # -- /seed-data ----------------------------------------------------------

    def test_seed_data_dry_run(self) -> None:
        result = asyncio.run(self._handler("seed-data")("--dry-run"))
        self.assertIn("Seed plan", result)
        self.assertIn("sample_users", result)

    def test_seed_data_execute(self) -> None:
        result = asyncio.run(self._handler("seed-data")(""))
        self.assertIn("Seeded", result)
        self.assertIn("development", result)

    def test_seed_data_env(self) -> None:
        result = asyncio.run(self._handler("seed-data")("--env testing --dry-run"))
        self.assertIn("testing", result)


if __name__ == "__main__":
    unittest.main()
