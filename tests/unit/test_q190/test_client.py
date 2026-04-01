"""Tests for LSPClient — Q190, task 1062."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from lidco.lsp.client import LSPClient, LSPCapability, _extract_capabilities, _encode_message


class TestLSPCapability(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(LSPCapability.GOTO_DEFINITION.value, "textDocument/definition")
        self.assertEqual(LSPCapability.FIND_REFERENCES.value, "textDocument/references")
        self.assertEqual(LSPCapability.HOVER.value, "textDocument/hover")
        self.assertEqual(LSPCapability.COMPLETION.value, "textDocument/completion")
        self.assertEqual(LSPCapability.DIAGNOSTICS.value, "textDocument/publishDiagnostics")
        self.assertEqual(LSPCapability.RENAME.value, "textDocument/rename")

    def test_enum_count(self):
        self.assertEqual(len(LSPCapability), 6)


class TestLSPClient(unittest.TestCase):
    def test_init_defaults(self):
        c = LSPClient("pyright-langserver")
        self.assertEqual(c._command, "pyright-langserver")
        self.assertEqual(c._args, ())
        self.assertFalse(c.is_running)
        self.assertEqual(c.capabilities, frozenset())

    def test_init_with_args(self):
        c = LSPClient("node", args=("server.js", "--stdio"))
        self.assertEqual(c._command, "node")
        self.assertEqual(c._args, ("server.js", "--stdio"))

    def test_is_running_no_process(self):
        c = LSPClient("fake")
        self.assertFalse(c.is_running)

    def test_is_running_with_dead_process(self):
        c = LSPClient("fake")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1
        c._process = mock_proc
        self.assertFalse(c.is_running)

    def test_is_running_with_live_process(self):
        c = LSPClient("fake")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        c._process = mock_proc
        self.assertTrue(c.is_running)

    @patch("lidco.lsp.client.subprocess.Popen")
    def test_start_file_not_found(self, mock_popen):
        mock_popen.side_effect = FileNotFoundError("not found")
        c = LSPClient("nonexistent-server")
        result = c.start()
        self.assertFalse(result)
        self.assertFalse(c.is_running)

    @patch("lidco.lsp.client.subprocess.Popen")
    def test_start_os_error(self, mock_popen):
        mock_popen.side_effect = OSError("failed")
        c = LSPClient("bad-server")
        result = c.start()
        self.assertFalse(result)

    def test_stop_no_process(self):
        c = LSPClient("fake")
        c.stop()  # should not raise
        self.assertFalse(c.is_running)

    def test_stop_clears_capabilities(self):
        c = LSPClient("fake")
        c._capabilities = frozenset(["textDocument/definition"])
        c._initialized = True
        c.stop()
        self.assertEqual(c.capabilities, frozenset())
        self.assertFalse(c._initialized)

    def test_stop_terminates_process(self):
        c = LSPClient("fake")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        c._process = mock_proc
        c.stop()
        mock_proc.terminate.assert_called_once()

    def test_send_request_not_running(self):
        c = LSPClient("fake")
        with self.assertRaises(RuntimeError):
            c.send_request("textDocument/hover", {})

    def test_capabilities_property_returns_frozenset(self):
        c = LSPClient("fake")
        caps = c.capabilities
        self.assertIsInstance(caps, frozenset)

    def test_start_already_running(self):
        c = LSPClient("fake")
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        c._process = mock_proc
        result = c.start()
        self.assertTrue(result)


class TestExtractCapabilities(unittest.TestCase):
    def test_empty_result(self):
        caps = _extract_capabilities({})
        self.assertEqual(caps, frozenset())

    def test_with_definition_provider(self):
        caps = _extract_capabilities({
            "capabilities": {"definitionProvider": True}
        })
        self.assertIn("textDocument/definition", caps)

    def test_with_multiple_providers(self):
        caps = _extract_capabilities({
            "capabilities": {
                "definitionProvider": True,
                "referencesProvider": True,
                "hoverProvider": True,
            }
        })
        self.assertEqual(len(caps), 3)

    def test_false_providers_excluded(self):
        caps = _extract_capabilities({
            "capabilities": {
                "definitionProvider": False,
                "hoverProvider": True,
            }
        })
        self.assertNotIn("textDocument/definition", caps)
        self.assertIn("textDocument/hover", caps)

    def test_non_dict_capabilities(self):
        caps = _extract_capabilities({"capabilities": "invalid"})
        self.assertEqual(caps, frozenset())


class TestEncodeMessage(unittest.TestCase):
    def test_basic_encoding(self):
        msg = _encode_message({"jsonrpc": "2.0", "id": 1, "method": "test"})
        self.assertIn(b"Content-Length:", msg)
        self.assertIn(b'"jsonrpc"', msg)

    def test_content_length_correct(self):
        import json
        body = {"jsonrpc": "2.0", "id": 1}
        msg = _encode_message(body)
        content = json.dumps(body).encode("utf-8")
        expected_header = f"Content-Length: {len(content)}\r\n\r\n"
        self.assertTrue(msg.startswith(expected_header.encode("ascii")))


if __name__ == "__main__":
    unittest.main()
