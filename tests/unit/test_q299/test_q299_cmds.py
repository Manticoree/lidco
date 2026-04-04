"""Tests for Q299 CLI commands (Q299)."""
import asyncio
import unittest

from lidco.cli.commands.q299_cmds import register_q299_commands


class _FakeRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ299Commands(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q299_commands(self.registry)

    # -- registration ---------------------------------------------------

    def test_all_commands_registered(self):
        expected = {"smart-commit", "split-commit", "validate-commit", "amend-safe"}
        self.assertEqual(set(self.registry.commands.keys()), expected)

    # -- /smart-commit --------------------------------------------------

    def test_smart_commit_no_args(self):
        result = asyncio.run(self.registry.commands["smart-commit"].handler(""))
        self.assertIn("Usage", result)

    def test_smart_commit_classify(self):
        diff = "--- a/tests/test_foo.py\n+++ b/tests/test_foo.py\n+pass"
        result = asyncio.run(
            self.registry.commands["smart-commit"].handler(f"--classify {diff}")
        )
        self.assertEqual(result, "test")

    def test_smart_commit_full_analysis(self):
        diff = "--- a/src/lidco/auth/x.py\n+++ b/src/lidco/auth/x.py\n+new line"
        result = asyncio.run(self.registry.commands["smart-commit"].handler(diff))
        self.assertIn("Category", result)
        self.assertIn("Suggested", result)

    # -- /split-commit --------------------------------------------------

    def test_split_commit_no_args(self):
        result = asyncio.run(self.registry.commands["split-commit"].handler(""))
        self.assertIn("Usage", result)

    def test_split_commit_by_file(self):
        result = asyncio.run(
            self.registry.commands["split-commit"].handler("--by-file a/x.py b/y.py")
        )
        self.assertIn("a", result)

    # -- /validate-commit -----------------------------------------------

    def test_validate_commit_no_args(self):
        result = asyncio.run(self.registry.commands["validate-commit"].handler(""))
        self.assertIn("Usage", result)

    def test_validate_commit_valid(self):
        result = asyncio.run(
            self.registry.commands["validate-commit"].handler("feat: add login")
        )
        self.assertIn("Valid", result)
        self.assertIn("yes", result)

    def test_validate_commit_invalid(self):
        result = asyncio.run(
            self.registry.commands["validate-commit"].handler("bad msg")
        )
        self.assertIn("no", result)

    # -- /amend-safe ----------------------------------------------------

    def test_amend_safe_no_args(self):
        result = asyncio.run(self.registry.commands["amend-safe"].handler(""))
        self.assertIn("Usage", result)

    def test_amend_safe_fixup(self):
        result = asyncio.run(
            self.registry.commands["amend-safe"].handler("fixup abc123 fix typo")
        )
        self.assertIn("Fixup created", result)

    def test_amend_safe_preserve(self):
        result = asyncio.run(
            self.registry.commands["amend-safe"].handler("preserve abc12345")
        )
        self.assertIn("Preserved", result)
        self.assertIn("refs/original/", result)

    def test_amend_safe_plan(self):
        result = asyncio.run(
            self.registry.commands["amend-safe"].handler("plan a b c")
        )
        self.assertIn("pick", result)

    def test_amend_safe_unknown_subcmd(self):
        result = asyncio.run(
            self.registry.commands["amend-safe"].handler("nope")
        )
        self.assertIn("Unknown", result)


if __name__ == "__main__":
    unittest.main()
