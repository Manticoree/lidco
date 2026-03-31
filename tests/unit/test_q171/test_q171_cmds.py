"""Tests for Q171 CLI commands."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest

from lidco.cli.commands import q171_cmds


def _run(coro):
    return asyncio.run(coro)


class TestQ171Commands(unittest.TestCase):
    def setUp(self):
        q171_cmds._state.clear()
        self.registered = {}

        class MockRegistry:
            def register(self_, cmd):
                self.registered[cmd.name] = cmd

        q171_cmds.register(MockRegistry())

    def test_commands_registered(self):
        self.assertIn("bare-mode", self.registered)
        self.assertIn("batch", self.registered)
        self.assertIn("ci-report", self.registered)

    # --- /bare-mode ---

    def test_bare_mode_on(self):
        result = _run(self.registered["bare-mode"].handler("on"))
        self.assertIn("activated", result.lower())

    def test_bare_mode_off(self):
        _run(self.registered["bare-mode"].handler("on"))
        result = _run(self.registered["bare-mode"].handler("off"))
        self.assertIn("deactivated", result.lower())

    def test_bare_mode_status(self):
        result = _run(self.registered["bare-mode"].handler("status"))
        data = json.loads(result)
        self.assertIn("active", data)

    def test_bare_mode_empty(self):
        result = _run(self.registered["bare-mode"].handler(""))
        data = json.loads(result)
        self.assertIn("active", data)

    def test_bare_mode_unknown(self):
        result = _run(self.registered["bare-mode"].handler("zzz"))
        self.assertIn("Usage", result)

    # --- /batch ---

    def test_batch_no_args(self):
        result = _run(self.registered["batch"].handler(""))
        self.assertIn("Usage", result)

    def test_batch_missing_file(self):
        result = _run(self.registered["batch"].handler("/nonexistent/file.txt"))
        self.assertIn("not found", result.lower())

    def test_batch_runs_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("prompt1\nprompt2\n")
            path = f.name
        try:
            result = _run(self.registered["batch"].handler(path))
            data = json.loads(result)
            self.assertEqual(data["total"], 2)
            self.assertEqual(data["success"], 2)
        finally:
            os.unlink(path)

    # --- /ci-report ---

    def test_ci_report(self):
        result = _run(self.registered["ci-report"].handler(""))
        self.assertIn("PASS", result)


if __name__ == "__main__":
    unittest.main()
