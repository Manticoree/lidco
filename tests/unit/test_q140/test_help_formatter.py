"""Tests for Q140 HelpFormatter."""
from __future__ import annotations

import unittest

from lidco.input.help_formatter import HelpFormatter, CommandHelp


class TestCommandHelp(unittest.TestCase):
    def test_defaults(self):
        c = CommandHelp(name="test", description="A test")
        self.assertEqual(c.usage, "")
        self.assertEqual(c.examples, [])
        self.assertEqual(c.aliases, [])


class TestHelpFormatter(unittest.TestCase):
    def setUp(self):
        self.fmt = HelpFormatter()
        self.fmt.register(CommandHelp(
            name="commit",
            description="Commit changes",
            usage="/commit [message]",
            examples=["/commit 'fix bug'", "/commit"],
            aliases=["ci"],
        ))
        self.fmt.register(CommandHelp(
            name="config",
            description="Show configuration",
            usage="/config [key]",
        ))
        self.fmt.register(CommandHelp(
            name="help",
            description="Show help",
        ))

    def test_format_command_found(self):
        text = self.fmt.format_command("commit")
        self.assertIn("/commit", text)
        self.assertIn("Commit changes", text)
        self.assertIn("Usage:", text)
        self.assertIn("Examples:", text)
        self.assertIn("Aliases:", text)

    def test_format_command_not_found(self):
        text = self.fmt.format_command("nonexistent")
        self.assertIn("Unknown command", text)

    def test_format_command_no_examples(self):
        text = self.fmt.format_command("help")
        self.assertNotIn("Examples:", text)

    def test_format_command_no_aliases(self):
        text = self.fmt.format_command("config")
        self.assertNotIn("Aliases:", text)

    def test_format_list_all(self):
        text = self.fmt.format_list()
        self.assertIn("commit", text)
        self.assertIn("config", text)
        self.assertIn("help", text)

    def test_format_list_filtered(self):
        text = self.fmt.format_list("co")
        self.assertIn("commit", text)
        self.assertIn("config", text)
        self.assertNotIn("help", text)

    def test_format_list_no_match(self):
        text = self.fmt.format_list("zzz")
        self.assertIn("No commands found", text)

    def test_format_list_sorted(self):
        text = self.fmt.format_list()
        lines = text.strip().split("\n")
        cmd_lines = [l.strip() for l in lines[1:]]
        names = [l.split()[0] for l in cmd_lines if l.startswith("/")]
        self.assertEqual(names, sorted(names))

    def test_format_group(self):
        text = self.fmt.format_group("Git", ["commit", "config"])
        self.assertIn("=== Git ===", text)
        self.assertIn("commit", text)
        self.assertIn("config", text)

    def test_format_group_missing_command(self):
        text = self.fmt.format_group("Tools", ["commit", "nonexistent"])
        self.assertIn("not registered", text)

    def test_search_by_name(self):
        results = self.fmt.search("comm")
        self.assertTrue(any(c.name == "commit" for c in results))

    def test_search_by_description(self):
        results = self.fmt.search("configuration")
        self.assertTrue(any(c.name == "config" for c in results))

    def test_search_empty(self):
        results = self.fmt.search("zzz")
        self.assertEqual(results, [])

    def test_search_sorted(self):
        results = self.fmt.search("co")
        names = [c.name for c in results]
        self.assertEqual(names, sorted(names))

    def test_register_overwrite(self):
        self.fmt.register(CommandHelp(name="commit", description="Updated"))
        text = self.fmt.format_command("commit")
        self.assertIn("Updated", text)

    def test_empty_formatter(self):
        fmt = HelpFormatter()
        text = fmt.format_list()
        self.assertIn("No commands found", text)

    def test_format_list_case_insensitive(self):
        text = self.fmt.format_list("COMMIT")
        self.assertIn("commit", text)

    def test_search_case_insensitive(self):
        results = self.fmt.search("HELP")
        self.assertTrue(any(c.name == "help" for c in results))

    def test_format_command_usage(self):
        text = self.fmt.format_command("commit")
        self.assertIn("/commit [message]", text)


if __name__ == "__main__":
    unittest.main()
