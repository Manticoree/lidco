"""Tests for Q141 CLI commands."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock

from lidco.cli.commands.q141_cmds import register, _state


def _run(coro):
    return asyncio.run(coro)


class TestRecoveryCommand(unittest.TestCase):
    def setUp(self):
        _state.clear()
        self.registry = MagicMock()
        self.registry.register = MagicMock()
        register(self.registry)
        self.handler = self.registry.register.call_args[0][0].handler

    def test_registered(self):
        cmd = self.registry.register.call_args[0][0]
        self.assertEqual(cmd.name, "recovery")

    def test_no_args_shows_usage(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_unknown_sub_shows_usage(self):
        result = _run(self.handler("unknown"))
        self.assertIn("Usage", result)

    # --- checkpoint save ---
    def test_checkpoint_save(self):
        result = _run(self.handler("checkpoint save test_label"))
        self.assertIn("Checkpoint saved", result)
        self.assertIn("test_label", result)

    def test_checkpoint_save_default_label(self):
        result = _run(self.handler("checkpoint save"))
        self.assertIn("manual", result)

    # --- checkpoint list ---
    def test_checkpoint_list_empty(self):
        result = _run(self.handler("checkpoint list"))
        self.assertIn("No checkpoints", result)

    def test_checkpoint_list_after_save(self):
        _run(self.handler("checkpoint save first"))
        result = _run(self.handler("checkpoint list"))
        self.assertIn("first", result)
        self.assertIn("Checkpoints (1)", result)

    # --- checkpoint restore ---
    def test_checkpoint_restore_missing_id(self):
        result = _run(self.handler("checkpoint restore"))
        self.assertIn("Usage", result)

    def test_checkpoint_restore_not_found(self):
        result = _run(self.handler("checkpoint restore nonexistent"))
        self.assertIn("not found", result)

    # --- checkpoint clear ---
    def test_checkpoint_clear(self):
        _run(self.handler("checkpoint save a"))
        result = _run(self.handler("checkpoint clear"))
        self.assertIn("cleared", result)
        result2 = _run(self.handler("checkpoint list"))
        self.assertIn("No checkpoints", result2)

    # --- checkpoint unknown action ---
    def test_checkpoint_unknown_action(self):
        result = _run(self.handler("checkpoint unknown"))
        self.assertIn("Usage", result)

    # --- repair ---
    def test_repair_empty_json(self):
        result = _run(self.handler("repair"))
        self.assertIn("Repaired", result)

    def test_repair_valid_data(self):
        data = json.dumps({"session_id": "s1", "created_at": 1.0, "messages": [], "status": "ok"})
        result = _run(self.handler(f"repair {data}"))
        self.assertIn("valid", result)

    def test_repair_invalid_json(self):
        result = _run(self.handler("repair {bad"))
        self.assertIn("Invalid JSON", result)

    # --- recover ---
    def test_recover_no_data(self):
        result = _run(self.handler("recover"))
        self.assertIn("No checkpoint data", result)

    def test_recover_with_data(self):
        _run(self.handler("checkpoint save test"))
        result = _run(self.handler("recover"))
        self.assertIn("source", result)

    # --- status ---
    def test_status_empty(self):
        result = _run(self.handler("status"))
        self.assertIn("Checkpoints: 0", result)
        self.assertIn("Latest: none", result)

    def test_status_with_checkpoint(self):
        _run(self.handler("checkpoint save mycp"))
        result = _run(self.handler("status"))
        self.assertIn("Checkpoints: 1", result)
        self.assertIn("mycp", result)


if __name__ == "__main__":
    unittest.main()
