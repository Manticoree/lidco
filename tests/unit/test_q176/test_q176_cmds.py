"""Tests for Q176 CLI commands — /classify, /rewrite, /auto-attach, /compress-context."""
from __future__ import annotations

import asyncio
import unittest

from lidco.input.intent_classifier import IntentClassifier
from lidco.input.prompt_rewriter import PromptRewriter
from lidco.input.auto_attach import AutoAttachResolver
from lidco.input.context_compressor import ContextCompressor
from lidco.cli.commands.q176_cmds import register_q176_commands


class FakeRegistry:
    def __init__(self):
        self.commands: dict = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ176Commands(unittest.TestCase):
    def setUp(self):
        self.registry = FakeRegistry()
        register_q176_commands(self.registry)

    def test_register_commands_count(self):
        self.assertEqual(len(self.registry.commands), 4)

    def test_register_classify(self):
        self.assertIn("classify", self.registry.commands)

    def test_register_rewrite(self):
        self.assertIn("rewrite", self.registry.commands)

    def test_register_auto_attach(self):
        self.assertIn("auto-attach", self.registry.commands)

    def test_register_compress_context(self):
        self.assertIn("compress-context", self.registry.commands)

    # --- classify handler ---
    def test_classify_handler_no_args(self):
        result = asyncio.run(self.registry.commands["classify"].handler(""))
        self.assertIn("Usage", result)

    def test_classify_handler_with_prompt(self):
        result = asyncio.run(self.registry.commands["classify"].handler("fix the bug"))
        self.assertIn("Intent:", result)
        self.assertIn("Confidence:", result)

    def test_classify_handler_shows_command(self):
        result = asyncio.run(self.registry.commands["classify"].handler("refactor the module"))
        self.assertIn("Suggested command:", result)

    # --- rewrite handler ---
    def test_rewrite_handler_no_args(self):
        result = asyncio.run(self.registry.commands["rewrite"].handler(""))
        self.assertIn("Usage", result)

    def test_rewrite_handler_specific_prompt(self):
        result = asyncio.run(self.registry.commands["rewrite"].handler("add login to auth.py"))
        self.assertIn("already specific", result)

    def test_rewrite_handler_vague_prompt(self):
        result = asyncio.run(self.registry.commands["rewrite"].handler("fix it"))
        self.assertIn("Rewritten:", result)

    # --- auto-attach handler ---
    def test_auto_attach_handler_no_args(self):
        result = asyncio.run(self.registry.commands["auto-attach"].handler(""))
        self.assertIn("Usage", result)

    def test_auto_attach_handler_no_matches(self):
        result = asyncio.run(self.registry.commands["auto-attach"].handler("fix auth"))
        self.assertIn("No implicit file references", result)

    # --- compress-context handler ---
    def test_compress_context_handler_no_args(self):
        result = asyncio.run(self.registry.commands["compress-context"].handler(""))
        self.assertIn("Usage", result)

    def test_compress_context_handler_with_code(self):
        code = "def foo():\n    return 1"
        result = asyncio.run(self.registry.commands["compress-context"].handler(code))
        self.assertIn("Original lines:", result)
        self.assertIn("Compressed lines:", result)


if __name__ == "__main__":
    unittest.main()
