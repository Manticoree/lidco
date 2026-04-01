"""Tests for cli.commands.q215_cmds — /vuln-scan, /audit-deps, /detect-secrets, /sast."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock


class TestQ215Commands(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registered = {}

        def capture(cmd):
            self.registered[cmd.name] = cmd

        self.registry.register = capture
        from lidco.cli.commands import q215_cmds

        q215_cmds.register(self.registry)

    def test_all_commands_registered(self):
        expected = {"vuln-scan", "audit-deps", "detect-secrets", "sast"}
        self.assertEqual(set(self.registered.keys()), expected)

    def test_vuln_scan_no_args(self):
        handler = self.registered["vuln-scan"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_vuln_scan_with_code(self):
        handler = self.registered["vuln-scan"].handler
        code = 'cursor.execute(f"SELECT * FROM t WHERE id={uid}")'
        result = asyncio.run(handler(code))
        self.assertIn("sql-injection", result.lower())

    def test_vuln_scan_clean(self):
        handler = self.registered["vuln-scan"].handler
        result = asyncio.run(handler("x = 1 + 2"))
        self.assertIn("No vulnerabilities", result)

    def test_audit_deps_no_args(self):
        handler = self.registered["audit-deps"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_audit_deps_no_version(self):
        handler = self.registered["audit-deps"].handler
        result = asyncio.run(handler("flask"))
        self.assertIn("No valid requirements", result)

    def test_detect_secrets_no_args(self):
        handler = self.registered["detect-secrets"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_detect_secrets_with_secret(self):
        handler = self.registered["detect-secrets"].handler
        code = 'password = "supersecretpass"'
        result = asyncio.run(handler(code))
        self.assertIn("detected", result.lower())

    def test_sast_no_args(self):
        handler = self.registered["sast"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_sast_with_flow(self):
        handler = self.registered["sast"].handler
        result = asyncio.run(handler("user_input -> db_exec"))
        self.assertIn("SAST findings", result)

    def test_sast_invalid_format(self):
        handler = self.registered["sast"].handler
        result = asyncio.run(handler("just some text"))
        self.assertIn("source_name -> sink_name", result)


if __name__ == "__main__":
    unittest.main()
