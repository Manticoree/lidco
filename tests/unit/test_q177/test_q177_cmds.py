"""Tests for Q177 CLI commands — /rich-diff, /explain-changes, /heatmap, /preview."""
from __future__ import annotations

import asyncio
import unittest

from lidco.ui.diff_renderer import DiffRenderer
from lidco.ui.change_explainer import ChangeExplainer
from lidco.ui.impact_heatmap import ImpactHeatmap
from lidco.ui.before_after import BeforeAfterPreview
from lidco.cli.commands.q177_cmds import register_q177_commands


class FakeRegistry:
    def __init__(self):
        self.commands: dict = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ177CommandRegistration(unittest.TestCase):
    def setUp(self):
        self.registry = FakeRegistry()
        register_q177_commands(self.registry)

    def test_register_commands_count(self):
        self.assertEqual(len(self.registry.commands), 4)

    def test_register_rich_diff(self):
        self.assertIn("rich-diff", self.registry.commands)

    def test_register_explain_changes(self):
        self.assertIn("explain-changes", self.registry.commands)

    def test_register_heatmap(self):
        self.assertIn("heatmap", self.registry.commands)

    def test_register_preview(self):
        self.assertIn("preview", self.registry.commands)


class TestQ177Handlers(unittest.TestCase):
    def setUp(self):
        self.registry = FakeRegistry()
        register_q177_commands(self.registry)

    def test_rich_diff_unified(self):
        result = asyncio.run(self.registry.commands["rich-diff"].handler("unified"))
        self.assertIn("Unified", result)

    def test_rich_diff_side_by_side(self):
        result = asyncio.run(self.registry.commands["rich-diff"].handler("side-by-side"))
        self.assertIn("Side-by-side", result)

    def test_rich_diff_word(self):
        result = asyncio.run(self.registry.commands["rich-diff"].handler("word"))
        self.assertIn("Word", result)

    def test_rich_diff_unknown_mode(self):
        result = asyncio.run(self.registry.commands["rich-diff"].handler("invalid"))
        self.assertIn("Unknown mode", result)

    def test_explain_changes_no_args(self):
        result = asyncio.run(self.registry.commands["explain-changes"].handler(""))
        self.assertIn("Usage", result)

    def test_explain_changes_with_args(self):
        result = asyncio.run(self.registry.commands["explain-changes"].handler("some changes"))
        self.assertIn("analysis", result.lower())

    def test_heatmap_no_args(self):
        result = asyncio.run(self.registry.commands["heatmap"].handler(""))
        self.assertIn("No files", result)

    def test_heatmap_with_path(self):
        result = asyncio.run(self.registry.commands["heatmap"].handler("src/"))
        self.assertIn("src/", result)

    def test_preview_no_args(self):
        result = asyncio.run(self.registry.commands["preview"].handler(""))
        self.assertIn("Usage", result)

    def test_preview_with_file(self):
        result = asyncio.run(self.registry.commands["preview"].handler("test.py"))
        self.assertIn("test.py", result)


if __name__ == "__main__":
    unittest.main()
