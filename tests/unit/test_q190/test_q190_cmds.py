"""Tests for Q190 CLI commands — Q190, task 1066."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from lidco.cli.commands import q190_cmds


class FakeRegistry:
    """Minimal registry mock that collects registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = handler


class TestQ190CmdsRegistration(unittest.TestCase):
    def setUp(self):
        self.registry = FakeRegistry()
        # Reset module-level state between tests
        q190_cmds._lsp_state.clear()
        q190_cmds.register_q190_commands(self.registry)

    def test_all_commands_registered(self):
        expected = {"lsp-start", "goto-def", "find-refs", "diagnostics"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    def test_lsp_start_no_args(self):
        handler = self.registry.commands["lsp-start"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_lsp_start_stop_no_server(self):
        handler = self.registry.commands["lsp-start"]
        result = asyncio.run(handler("stop"))
        self.assertIn("No LSP server", result)

    def test_lsp_start_status_no_server(self):
        handler = self.registry.commands["lsp-start"]
        result = asyncio.run(handler("status"))
        self.assertIn("not running", result)

    @patch("lidco.lsp.client.LSPClient")
    def test_lsp_start_success(self, MockClient):
        mock_inst = MagicMock()
        mock_inst.start.return_value = True
        mock_inst.capabilities = frozenset(["textDocument/definition"])
        MockClient.return_value = mock_inst

        handler = self.registry.commands["lsp-start"]
        with patch.object(q190_cmds, "LSPClient", MockClient, create=True):
            # We need to patch the import inside the handler
            with patch("lidco.lsp.client.LSPClient", MockClient):
                result = asyncio.run(handler("pyright --stdio"))
        self.assertIn("started" if "started" in result.lower() else "pyright", result.lower())

    def test_goto_def_no_args(self):
        handler = self.registry.commands["goto-def"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_goto_def_no_server(self):
        handler = self.registry.commands["goto-def"]
        result = asyncio.run(handler("file.py 10 5"))
        self.assertIn("No LSP server", result)

    def test_goto_def_with_server(self):
        mock_client = MagicMock()
        q190_cmds._lsp_state["client"] = mock_client

        with patch("lidco.lsp.definitions.DefinitionResolver") as MockResolver:
            from lidco.lsp.definitions import Location
            mock_resolver = MagicMock()
            mock_resolver.goto_definition.return_value = Location(file="/src/foo.py", line=10, column=4)
            MockResolver.return_value = mock_resolver

            handler = self.registry.commands["goto-def"]
            result = asyncio.run(handler("file.py 5 3"))
            self.assertIn("Definition", result)

    def test_goto_def_invalid_numbers(self):
        q190_cmds._lsp_state["client"] = MagicMock()
        handler = self.registry.commands["goto-def"]
        result = asyncio.run(handler("file.py abc def"))
        self.assertIn("integers", result)

    def test_find_refs_no_args(self):
        handler = self.registry.commands["find-refs"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_find_refs_no_server(self):
        handler = self.registry.commands["find-refs"]
        result = asyncio.run(handler("file.py 10 5"))
        self.assertIn("No LSP server", result)

    def test_find_refs_symbols_no_server(self):
        handler = self.registry.commands["find-refs"]
        result = asyncio.run(handler("--symbols MyClass"))
        self.assertIn("No LSP server", result)

    def test_diagnostics_no_args(self):
        handler = self.registry.commands["diagnostics"]
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_diagnostics_no_server(self):
        handler = self.registry.commands["diagnostics"]
        result = asyncio.run(handler("file.py"))
        self.assertIn("No LSP server", result)

    def test_diagnostics_summary_no_server(self):
        handler = self.registry.commands["diagnostics"]
        result = asyncio.run(handler("--summary"))
        self.assertIn("No LSP server", result)

    def test_diagnostics_all_no_server(self):
        handler = self.registry.commands["diagnostics"]
        result = asyncio.run(handler("--all"))
        self.assertIn("No LSP server", result)

    def test_goto_def_type_mode(self):
        q190_cmds._lsp_state["client"] = MagicMock()
        handler = self.registry.commands["goto-def"]
        with patch("lidco.lsp.definitions.DefinitionResolver") as MockResolver:
            mock_resolver = MagicMock()
            mock_resolver.goto_type_definition.return_value = None
            MockResolver.return_value = mock_resolver
            result = asyncio.run(handler("--type file.py 5 3"))
            self.assertIn("No type definition", result)

    def test_goto_def_impl_mode(self):
        q190_cmds._lsp_state["client"] = MagicMock()
        handler = self.registry.commands["goto-def"]
        with patch("lidco.lsp.definitions.DefinitionResolver") as MockResolver:
            mock_resolver = MagicMock()
            mock_resolver.goto_implementation.return_value = []
            MockResolver.return_value = mock_resolver
            result = asyncio.run(handler("--impl file.py 5 3"))
            self.assertIn("No implementations", result)


if __name__ == "__main__":
    unittest.main()
