"""Tests for cc_mcp_adapter (Task 953)."""
from __future__ import annotations

import unittest

from lidco.compat.cc_mcp_adapter import CCMCPServer, parse_cc_mcp_config, to_lidco_mcp_config


class TestCCMCPServer(unittest.TestCase):
    def test_defaults(self):
        s = CCMCPServer()
        self.assertEqual(s.name, "")
        self.assertEqual(s.transport, "stdio")
        self.assertIsNone(s.url)
        self.assertEqual(s.args, [])
        self.assertEqual(s.env, {})


class TestParseCCMCPConfig(unittest.TestCase):
    def test_stdio_server(self):
        settings = {
            "mcpServers": {
                "my-tool": {
                    "command": "npx",
                    "args": ["-y", "my-tool"],
                    "env": {"KEY": "val"},
                }
            }
        }
        servers = parse_cc_mcp_config(settings)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].name, "my-tool")
        self.assertEqual(servers[0].command, "npx")
        self.assertEqual(servers[0].args, ["-y", "my-tool"])
        self.assertEqual(servers[0].transport, "stdio")
        self.assertEqual(servers[0].env, {"KEY": "val"})

    def test_sse_server(self):
        settings = {
            "mcpServers": {
                "remote": {
                    "transport": "sse",
                    "url": "https://mcp.example.com/sse",
                }
            }
        }
        servers = parse_cc_mcp_config(settings)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].transport, "sse")
        self.assertEqual(servers[0].url, "https://mcp.example.com/sse")

    def test_streamable_http(self):
        settings = {
            "mcpServers": {
                "http-srv": {
                    "transport": "streamable-http",
                    "url": "https://mcp.example.com/stream",
                }
            }
        }
        servers = parse_cc_mcp_config(settings)
        self.assertEqual(servers[0].transport, "streamable-http")
        self.assertEqual(servers[0].url, "https://mcp.example.com/stream")

    def test_infer_sse_from_url(self):
        settings = {
            "mcpServers": {
                "inferred": {"url": "https://x.com/sse"}
            }
        }
        servers = parse_cc_mcp_config(settings)
        self.assertEqual(servers[0].transport, "sse")

    def test_empty_mcp_servers(self):
        self.assertEqual(parse_cc_mcp_config({"mcpServers": {}}), [])

    def test_no_mcp_servers_key(self):
        self.assertEqual(parse_cc_mcp_config({}), [])

    def test_non_dict_server_entry_skipped(self):
        settings = {"mcpServers": {"bad": "not-a-dict"}}
        self.assertEqual(parse_cc_mcp_config(settings), [])

    def test_non_dict_mcp_servers_returns_empty(self):
        self.assertEqual(parse_cc_mcp_config({"mcpServers": "bad"}), [])

    def test_rejects_non_dict_settings(self):
        with self.assertRaises(TypeError):
            parse_cc_mcp_config("not a dict")  # type: ignore[arg-type]

    def test_multiple_servers(self):
        settings = {
            "mcpServers": {
                "a": {"command": "a-cmd"},
                "b": {"url": "https://b.com"},
            }
        }
        servers = parse_cc_mcp_config(settings)
        self.assertEqual(len(servers), 2)
        names = {s.name for s in servers}
        self.assertEqual(names, {"a", "b"})


class TestToLidcoMCPConfig(unittest.TestCase):
    def test_stdio_conversion(self):
        servers = [CCMCPServer(name="t", command="cmd", args=["--flag"], env={"K": "V"}, transport="stdio")]
        result = to_lidco_mcp_config(servers)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "t")
        self.assertEqual(result[0]["command"], "cmd")
        self.assertEqual(result[0]["args"], ["--flag"])
        self.assertEqual(result[0]["env"], {"K": "V"})
        self.assertEqual(result[0]["transport"], "stdio")

    def test_sse_conversion(self):
        servers = [CCMCPServer(name="r", transport="sse", url="https://x.com")]
        result = to_lidco_mcp_config(servers)
        self.assertEqual(result[0]["url"], "https://x.com")
        self.assertNotIn("command", result[0])

    def test_streamable_http_conversion(self):
        servers = [CCMCPServer(name="s", transport="streamable-http", url="https://y.com")]
        result = to_lidco_mcp_config(servers)
        self.assertEqual(result[0]["transport"], "streamable-http")
        self.assertEqual(result[0]["url"], "https://y.com")

    def test_empty_list(self):
        self.assertEqual(to_lidco_mcp_config([]), [])

    def test_stdio_no_env(self):
        servers = [CCMCPServer(name="n", command="c", transport="stdio")]
        result = to_lidco_mcp_config(servers)
        self.assertNotIn("env", result[0])
