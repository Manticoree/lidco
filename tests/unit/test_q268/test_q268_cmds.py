"""Tests for Q268 CLI commands."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


def _run(coro):
    return asyncio.run(coro)


class TestQ268Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def _register(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = _register
        from lidco.cli.commands.q268_cmds import register
        register(self.registry)

    def test_all_commands_registered(self):
        expected = {"dlp-scan", "content-filter", "watermark", "dlp-policy"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_dlp_scan_no_args(self):
        result = _run(self.registered["dlp-scan"].handler(""))
        self.assertIn("Usage", result)

    def test_dlp_scan_with_content(self):
        result = _run(self.registered["dlp-scan"].handler("test@example.com"))
        self.assertIn("Finding", result)

    def test_content_filter_no_args(self):
        result = _run(self.registered["content-filter"].handler(""))
        self.assertIn("Usage", result)

    def test_content_filter_list(self):
        result = _run(self.registered["content-filter"].handler("list"))
        self.assertIn("No rules", result)

    def test_watermark_no_args(self):
        result = _run(self.registered["watermark"].handler(""))
        self.assertIn("Usage", result)

    def test_watermark_embed(self):
        result = _run(self.registered["watermark"].handler("embed print('hi')"))
        self.assertIn("Watermarked", result)

    def test_dlp_policy_no_args(self):
        result = _run(self.registered["dlp-policy"].handler(""))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
