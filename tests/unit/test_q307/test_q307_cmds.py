"""Tests for Q307 CLI commands."""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from lidco.cli.commands.q307_cmds import register_q307_commands


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, desc: str, handler) -> None:
        self.commands[name] = (desc, handler)


class TestQ307CommandRegistration(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q307_commands(self.registry)

    def test_all_commands_registered(self):
        expected = {"codeowners", "ownership-analyze", "review-route", "knowledge-transfer"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    def test_descriptions_non_empty(self):
        for name, (desc, _) in self.registry.commands.items():
            self.assertTrue(desc, f"Command '{name}' has empty description")


class TestCodeownersHandler(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q307_commands(self.registry)
        self.handler = self.registry.commands["codeowners"][1]

    @patch("lidco.ownership.generator.CodeownersGenerator.generate_from_git")
    def test_generate_default(self, mock_gen):
        from lidco.ownership.generator import CodeownersEntry, CodeownersResult
        mock_gen.return_value = CodeownersResult(
            entries=[CodeownersEntry("/src/", ["@backend"])],
        )
        result = asyncio.run(self.handler(""))
        self.assertIn("Generated CODEOWNERS", result)
        self.assertIn("1 entries", result)

    @patch("lidco.ownership.generator.CodeownersGenerator.generate_from_git")
    def test_generate_empty(self, mock_gen):
        from lidco.ownership.generator import CodeownersResult
        mock_gen.return_value = CodeownersResult()
        result = asyncio.run(self.handler(""))
        self.assertIn("No ownership data", result)

    @patch("lidco.ownership.generator.CodeownersGenerator.generate_from_git")
    def test_show_subcommand(self, mock_gen):
        from lidco.ownership.generator import CodeownersEntry, CodeownersResult
        mock_gen.return_value = CodeownersResult(
            entries=[CodeownersEntry("/src/", ["@team"])],
        )
        result = asyncio.run(self.handler("show"))
        self.assertIn("/src/ @team", result)

    @patch("lidco.ownership.generator.CodeownersGenerator.generate_from_git")
    def test_unknown_subcommand(self, mock_gen):
        from lidco.ownership.generator import CodeownersResult
        mock_gen.return_value = CodeownersResult()
        result = asyncio.run(self.handler("unknown"))
        # "unknown" is treated as a path for generate, not a real subcommand error
        self.assertIsInstance(result, str)


class TestOwnershipAnalyzeHandler(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q307_commands(self.registry)
        self.handler = self.registry.commands["ownership-analyze"][1]

    @patch("lidco.ownership.generator.CodeownersGenerator._blame_file")
    @patch("lidco.ownership.generator.CodeownersGenerator._list_tracked_files")
    @patch("lidco.ownership.generator.CodeownersGenerator.generate_from_git")
    def test_summary_default(self, mock_gen, mock_list, mock_blame):
        from lidco.ownership.generator import BlameEntry, CodeownersResult
        mock_gen.return_value = CodeownersResult()
        mock_list.return_value = ["a.py"]
        mock_blame.return_value = [BlameEntry("a.py", "alice", 100)]
        result = asyncio.run(self.handler(""))
        self.assertIn("Ownership Analysis", result)
        self.assertIn("bus factor", result.lower())

    @patch("lidco.ownership.generator.CodeownersGenerator._blame_file")
    @patch("lidco.ownership.generator.CodeownersGenerator._list_tracked_files")
    @patch("lidco.ownership.generator.CodeownersGenerator.generate_from_git")
    def test_bus_factor_subcommand(self, mock_gen, mock_list, mock_blame):
        from lidco.ownership.generator import BlameEntry, CodeownersResult
        mock_gen.return_value = CodeownersResult()
        mock_list.return_value = ["a.py"]
        mock_blame.return_value = [BlameEntry("a.py", "alice", 100)]
        result = asyncio.run(self.handler("bus-factor"))
        self.assertIn("Bus Factor", result)


class TestReviewRouteHandler(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q307_commands(self.registry)
        self.handler = self.registry.commands["review-route"][1]

    def test_no_args_shows_usage(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_route_files(self):
        result = asyncio.run(self.handler("src/main.py"))
        # With empty router, files are unassigned
        self.assertIn("unassigned", result.lower())

    def test_round_robin_empty(self):
        result = asyncio.run(self.handler("round-robin backend"))
        self.assertIn("No available", result)

    def test_least_loaded_empty(self):
        result = asyncio.run(self.handler("least-loaded backend"))
        self.assertIn("No available", result)


class TestKnowledgeTransferHandler(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q307_commands(self.registry)
        self.handler = self.registry.commands["knowledge-transfer"][1]

    @patch("lidco.ownership.generator.CodeownersGenerator._blame_file")
    @patch("lidco.ownership.generator.CodeownersGenerator._list_tracked_files")
    def test_summary_default(self, mock_list, mock_blame):
        from lidco.ownership.generator import BlameEntry
        mock_list.return_value = ["a.py"]
        mock_blame.return_value = [BlameEntry("a.py", "alice", 100)]
        result = asyncio.run(self.handler(""))
        self.assertIn("Knowledge Transfer Plan", result)

    @patch("lidco.ownership.generator.CodeownersGenerator._blame_file")
    @patch("lidco.ownership.generator.CodeownersGenerator._list_tracked_files")
    def test_critical_subcommand(self, mock_list, mock_blame):
        from lidco.ownership.generator import BlameEntry
        mock_list.return_value = ["a.py"]
        mock_blame.return_value = [BlameEntry("a.py", "alice", 100)]
        result = asyncio.run(self.handler("critical"))
        self.assertIsInstance(result, str)

    @patch("lidco.ownership.generator.CodeownersGenerator._blame_file")
    @patch("lidco.ownership.generator.CodeownersGenerator._list_tracked_files")
    def test_pairings_subcommand(self, mock_list, mock_blame):
        from lidco.ownership.generator import BlameEntry
        mock_list.return_value = []
        mock_blame.return_value = []
        result = asyncio.run(self.handler("pairings"))
        self.assertIn("No pairing", result)

    @patch("lidco.ownership.generator.CodeownersGenerator._blame_file")
    @patch("lidco.ownership.generator.CodeownersGenerator._list_tracked_files")
    def test_doc_gaps_subcommand(self, mock_list, mock_blame):
        mock_list.return_value = []
        mock_blame.return_value = []
        result = asyncio.run(self.handler("doc-gaps"))
        self.assertIn("No documentation gaps", result)


if __name__ == "__main__":
    unittest.main()
