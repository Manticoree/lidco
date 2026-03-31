"""Tests for lidco.cli.commands.q160_cmds — Q160 Task 916."""

from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.registry import CommandRegistry


class TestQ160Commands(unittest.TestCase):
    def setUp(self):
        # Reset module-level state between tests
        import lidco.cli.commands.q160_cmds as mod
        mod._state.clear()
        self.registry = CommandRegistry()

    def _run(self, name: str, args: str = "") -> str:
        cmd = self.registry.get(name)
        self.assertIsNotNone(cmd, f"Command '/{name}' not found")
        return asyncio.run(cmd.handler(args))

    # -- /auto-mode ---------------------------------------------------------

    def test_auto_mode_registered(self):
        self.assertIsNotNone(self.registry.get("auto-mode"))

    def test_auto_mode_on(self):
        result = self._run("auto-mode", "on")
        self.assertIn("enabled", result)

    def test_auto_mode_off(self):
        self._run("auto-mode", "on")
        result = self._run("auto-mode", "off")
        self.assertIn("disabled", result)

    def test_auto_mode_status(self):
        result = self._run("auto-mode", "status")
        self.assertIn("Auto-mode", result)
        self.assertIn("Rules", result)

    def test_auto_mode_add_rule(self):
        result = self._run("auto-mode", "add-rule allow network")
        self.assertIn("Rule added", result)

    def test_auto_mode_remove_rule(self):
        self._run("auto-mode", "add-rule allow network")
        result = self._run("auto-mode", "remove-rule allow network")
        self.assertIn("Rule removed", result)

    def test_auto_mode_usage(self):
        result = self._run("auto-mode", "")
        self.assertIn("Usage", result)

    # -- /checkpoint --------------------------------------------------------

    def test_checkpoint_registered(self):
        self.assertIsNotNone(self.registry.get("checkpoint"))

    def test_checkpoint_create(self):
        result = self._run("checkpoint", "my-label")
        self.assertIn("Checkpoint created", result)
        self.assertIn("my-label", result)

    def test_checkpoint_create_no_label(self):
        result = self._run("checkpoint", "")
        self.assertIn("Checkpoint created", result)

    # -- /checkpoints -------------------------------------------------------

    def test_checkpoints_registered(self):
        self.assertIsNotNone(self.registry.get("checkpoints"))

    def test_checkpoints_list_empty(self):
        result = self._run("checkpoints", "list")
        self.assertIn("No checkpoints", result)

    def test_checkpoints_list_after_create(self):
        self._run("checkpoint", "test-cp")
        result = self._run("checkpoints", "list")
        self.assertIn("Checkpoints (1)", result)

    def test_checkpoints_clear(self):
        self._run("checkpoint", "x")
        result = self._run("checkpoints", "clear")
        self.assertIn("cleared", result)

    def test_checkpoints_default_is_list(self):
        result = self._run("checkpoints", "")
        self.assertIn("No checkpoints", result)

    # -- /rewind ------------------------------------------------------------

    def test_rewind_registered(self):
        self.assertIsNotNone(self.registry.get("rewind"))

    def test_rewind_usage(self):
        result = self._run("rewind", "")
        self.assertIn("Usage", result)

    def test_rewind_invalid_mode(self):
        result = self._run("rewind", "invalid abc123")
        self.assertIn("Invalid mode", result)

    def test_rewind_missing_checkpoint(self):
        result = self._run("rewind", "code nonexistent")
        self.assertIn("not found", result)

    def test_rewind_chat(self):
        self._run("checkpoint", "cp1")
        # Get the checkpoint id from listing
        listing = self._run("checkpoints", "list")
        # Extract id — format: "  <id> [label] (N files)"
        import re
        match = re.search(r"  (\w+)", listing)
        self.assertIsNotNone(match)
        cp_id = match.group(1)
        result = self._run("rewind", f"chat {cp_id}")
        self.assertIn("truncated to position", result)

    def test_rewind_both(self):
        self._run("checkpoint", "cp2")
        listing = self._run("checkpoints", "list")
        import re
        match = re.search(r"  (\w+)", listing)
        self.assertIsNotNone(match)
        cp_id = match.group(1)
        result = self._run("rewind", f"both {cp_id}")
        self.assertIn("Rewind complete", result)


if __name__ == "__main__":
    unittest.main()
