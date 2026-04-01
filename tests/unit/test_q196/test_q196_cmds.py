"""Tests for cli.commands.q196_cmds — /agent-summary, /magic-docs, /readme-gen, /doc-sync."""
from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from unittest.mock import MagicMock


class TestQ196Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q196_cmds

        q196_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"agent-summary", "magic-docs", "readme-gen", "doc-sync"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_agent_summary_init(self):
        handler = self.registered["agent-summary"].handler
        result = asyncio.run(handler("mybot"))
        self.assertIn("initialized", result.lower())
        self.assertIn("mybot", result)

    def test_agent_summary_show(self):
        handler = self.registered["agent-summary"].handler
        asyncio.run(handler("bot"))  # init
        result = asyncio.run(handler(""))  # show
        self.assertIn("Agent Summary", result)

    def test_magic_docs_no_args(self):
        handler = self.registered["magic-docs"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_magic_docs_with_file(self):
        handler = self.registered["magic-docs"].handler
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False)
        f.write('"""Module doc."""\ndef foo(): pass\n')
        f.close()
        try:
            result = asyncio.run(handler(f.name))
            self.assertIn("Module Overview", result)
        finally:
            os.unlink(f.name)

    def test_magic_docs_nonexistent(self):
        handler = self.registered["magic-docs"].handler
        result = asyncio.run(handler("/nonexistent.py"))
        self.assertIn("No documentation", result)

    def test_readme_gen(self):
        handler = self.registered["readme-gen"].handler
        result = asyncio.run(handler(". TestProject"))
        self.assertIn("# TestProject", result)

    def test_readme_gen_default(self):
        handler = self.registered["readme-gen"].handler
        result = asyncio.run(handler(""))
        self.assertIn("# MyProject", result)

    def test_doc_sync_no_docs(self):
        handler = self.registered["doc-sync"].handler
        with tempfile.TemporaryDirectory() as td:
            result = asyncio.run(handler(td))
            self.assertIn("No documentation", result)

    def test_doc_sync_with_docs(self):
        handler = self.registered["doc-sync"].handler
        with tempfile.TemporaryDirectory() as td:
            docs_dir = os.path.join(td, "docs")
            os.makedirs(docs_dir)
            with open(os.path.join(docs_dir, "api.md"), "w") as f:
                f.write("# API\n")
            result = asyncio.run(handler(td))
            self.assertIn("Total docs", result)

    def test_all_commands_have_descriptions(self):
        for name, cmd in self.registered.items():
            self.assertIsInstance(cmd.description, str)
            self.assertTrue(len(cmd.description) > 0)

    def test_all_commands_have_handlers(self):
        for name, cmd in self.registered.items():
            self.assertTrue(callable(cmd.handler))

    def test_agent_summary_default_name(self):
        handler = self.registered["agent-summary"].handler
        result = asyncio.run(handler(""))
        # First call should init with default name
        self.assertIsInstance(result, str)

    def test_readme_gen_includes_install(self):
        handler = self.registered["readme-gen"].handler
        result = asyncio.run(handler(". MyPkg"))
        self.assertIn("pip install", result)

    def test_readme_gen_includes_badge(self):
        handler = self.registered["readme-gen"].handler
        result = asyncio.run(handler(". MyPkg"))
        self.assertIn("build", result.lower())


if __name__ == "__main__":
    unittest.main()
