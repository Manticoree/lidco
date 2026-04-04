"""Tests for lidco.cli.commands.q289_cmds."""
from __future__ import annotations

import asyncio
import unittest

from lidco.cli.commands.q289_cmds import register_q289_commands


class _FakeRegistry:
    """Minimal registry that captures registered commands."""

    def __init__(self):
        self.commands: dict[str, object] = {}

    def register(self, cmd):
        self.commands[cmd.name] = cmd


class TestQ289Commands(unittest.TestCase):
    def setUp(self):
        self.registry = _FakeRegistry()
        register_q289_commands(self.registry)

    def test_commands_registered(self):
        names = set(self.registry.commands.keys())
        self.assertIn("gh-pr", names)
        self.assertIn("gh-issue", names)
        self.assertIn("gh-actions", names)
        self.assertIn("gh-review", names)

    # -- /gh-pr -----------------------------------------------------------

    def test_gh_pr_usage(self):
        handler = self.registry.commands["gh-pr"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_gh_pr_create(self):
        handler = self.registry.commands["gh-pr"].handler
        result = asyncio.run(handler("create my-title body feat main"))
        self.assertIn("PR #1", result)
        self.assertIn("my-title", result)

    def test_gh_pr_create_missing_title(self):
        handler = self.registry.commands["gh-pr"].handler
        result = asyncio.run(handler("create"))
        self.assertIn("Usage", result)

    def test_gh_pr_describe(self):
        handler = self.registry.commands["gh-pr"].handler
        result = asyncio.run(handler("describe +added"))
        self.assertIn("addition", result)

    # -- /gh-issue --------------------------------------------------------

    def test_gh_issue_usage(self):
        handler = self.registry.commands["gh-issue"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_gh_issue_create(self):
        handler = self.registry.commands["gh-issue"].handler
        result = asyncio.run(handler("create bug-title"))
        self.assertIn("Issue #1", result)

    def test_gh_issue_list_empty(self):
        handler = self.registry.commands["gh-issue"].handler
        result = asyncio.run(handler("list"))
        self.assertIn("No issues", result)

    # -- /gh-actions ------------------------------------------------------

    def test_gh_actions_usage(self):
        handler = self.registry.commands["gh-actions"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_gh_actions_list_no_repo(self):
        handler = self.registry.commands["gh-actions"].handler
        result = asyncio.run(handler("list"))
        self.assertIn("Usage", result)

    def test_gh_actions_list_repo(self):
        handler = self.registry.commands["gh-actions"].handler
        result = asyncio.run(handler("list owner/repo"))
        self.assertIn("No runs", result)

    # -- /gh-review -------------------------------------------------------

    def test_gh_review_usage(self):
        handler = self.registry.commands["gh-review"].handler
        result = asyncio.run(handler(""))
        self.assertIn("Usage", result)

    def test_gh_review_request(self):
        handler = self.registry.commands["gh-review"].handler
        result = asyncio.run(handler("request 1 alice bob"))
        self.assertIn("Requested reviewers", result)
        self.assertIn("alice", result)

    def test_gh_review_list_empty(self):
        handler = self.registry.commands["gh-review"].handler
        result = asyncio.run(handler("list 999"))
        self.assertIn("No reviews", result)


if __name__ == "__main__":
    unittest.main()
