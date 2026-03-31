"""Tests for cc_conventions (Task 954)."""
from __future__ import annotations

import json
import unittest

from lidco.compat.cc_conventions import CCProjectConfig, scan_claude_dir


class TestCCProjectConfig(unittest.TestCase):
    def test_defaults(self):
        c = CCProjectConfig()
        self.assertEqual(c.instructions, "")
        self.assertEqual(c.settings, {})
        self.assertEqual(c.commands, [])
        self.assertEqual(c.hooks, [])
        self.assertEqual(c.mcp_servers, [])


class TestScanClaudeDir(unittest.TestCase):
    def _make_read_fn(self, files: dict[str, str | None]):
        """Create a fake read_fn from a dict of path -> content."""
        import os

        def read_fn(path: str) -> str | None:
            # Normalize separators for matching
            norm = path.replace("\\", "/")
            for k, v in files.items():
                if norm.endswith(k.replace("\\", "/")):
                    return v
            return None
        return read_fn

    def test_finds_claude_md_at_root(self):
        read_fn = self._make_read_fn({"CLAUDE.md": "# Instructions here"})
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(config.instructions, "# Instructions here")

    def test_finds_claude_md_in_dot_claude(self):
        read_fn = self._make_read_fn({".claude/CLAUDE.md": "# From .claude"})
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(config.instructions, "# From .claude")

    def test_root_claude_md_takes_priority(self):
        read_fn = self._make_read_fn({
            "CLAUDE.md": "root",
            ".claude/CLAUDE.md": "nested",
        })
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(config.instructions, "root")

    def test_no_instructions(self):
        read_fn = self._make_read_fn({})
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(config.instructions, "")

    def test_parses_settings_json(self):
        settings = {"allowedTools": ["Read", "Write"], "mcpServers": {}}
        read_fn = self._make_read_fn({
            ".claude/settings.json": json.dumps(settings),
        })
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(config.settings["allowedTools"], ["Read", "Write"])

    def test_invalid_settings_json(self):
        read_fn = self._make_read_fn({".claude/settings.json": "not-json"})
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(config.settings, {})

    def test_local_settings_override(self):
        settings = {"key1": "val1", "key2": "val2"}
        local = {"key2": "overridden", "key3": "new"}
        read_fn = self._make_read_fn({
            ".claude/settings.json": json.dumps(settings),
            ".claude/settings.local.json": json.dumps(local),
        })
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(config.settings["key1"], "val1")
        self.assertEqual(config.settings["key2"], "overridden")
        self.assertEqual(config.settings["key3"], "new")

    def test_mcp_servers_extracted(self):
        settings = {
            "mcpServers": {
                "tool1": {"command": "npx", "args": ["tool1"]},
            }
        }
        read_fn = self._make_read_fn({
            ".claude/settings.json": json.dumps(settings),
        })
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(len(config.mcp_servers), 1)
        self.assertEqual(config.mcp_servers[0]["name"], "tool1")

    def test_hooks_extracted(self):
        settings = {
            "hooks": {
                "PreToolUse": [{"command": "echo pre", "matcher": "Bash"}],
                "Stop": ["echo bye"],
            }
        }
        read_fn = self._make_read_fn({
            ".claude/settings.json": json.dumps(settings),
        })
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(len(config.hooks), 2)
        events = [h["event"] for h in config.hooks]
        self.assertIn("PreToolUse", events)
        self.assertIn("Stop", events)

    def test_hooks_string_format(self):
        settings = {"hooks": {"Stop": ["echo done"]}}
        read_fn = self._make_read_fn({
            ".claude/settings.json": json.dumps(settings),
        })
        config = scan_claude_dir("/project", read_fn=read_fn)
        self.assertEqual(config.hooks[0]["command"], "echo done")
