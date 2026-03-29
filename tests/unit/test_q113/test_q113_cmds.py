"""Tests for Q113 CLI commands (Task 701b)."""
import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from lidco.cli.commands.q113_cmds import register


def _make_registry():
    """Create a mock registry that captures registered commands."""
    commands = {}

    class MockRegistry:
        def register(self, cmd):
            commands[cmd.name] = cmd

    reg = MockRegistry()
    register(reg)
    return commands


class TestRegistration(unittest.TestCase):
    def test_all_commands_registered(self):
        cmds = _make_registry()
        self.assertIn("bugbot", cmds)
        self.assertIn("session-tags", cmds)
        self.assertIn("lint-hook", cmds)

    def test_bugbot_description(self):
        cmds = _make_registry()
        self.assertIn("BugBot", cmds["bugbot"].description)

    def test_session_tags_description(self):
        cmds = _make_registry()
        self.assertIn("tag", cmds["session-tags"].description.lower())

    def test_lint_hook_description(self):
        cmds = _make_registry()
        self.assertIn("lint", cmds["lint-hook"].description.lower())


class TestBugbotHandler(unittest.TestCase):
    def setUp(self):
        self.cmds = _make_registry()
        self.handler = self.cmds["bugbot"].handler

    def test_usage_no_args(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_check_no_diff(self):
        result = asyncio.run(self.handler("check"))
        self.assertIn("Usage", result)

    def test_check_clean_diff(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+x = 42"
        result = asyncio.run(self.handler(f"check {diff}"))
        self.assertIn("No issues", result)

    def test_check_with_findings(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+except:"
        result = asyncio.run(self.handler(f"check {diff}"))
        self.assertIn("issue", result.lower())
        self.assertIn("bare_except", result)

    def test_check_eval_detected(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n+eval(x)"
        result = asyncio.run(self.handler(f"check {diff}"))
        self.assertIn("eval", result.lower())

    def test_fix_no_args(self):
        result = asyncio.run(self.handler("fix"))
        self.assertIn("Usage", result)

    def test_fix_invalid_json(self):
        result = asyncio.run(self.handler("fix not_json"))
        self.assertIn("Invalid JSON", result)

    def test_fix_valid_json(self):
        finding = json.dumps({
            "file": "test.py",
            "line": 5,
            "severity": "medium",
            "message": "bare except",
            "rule_id": "bare_except",
            "source": "try:\n    x()\nexcept:\n    pass",
        })
        result = asyncio.run(self.handler(f"fix {finding}"))
        self.assertIn("Fix proposal", result)
        self.assertIn("bare_except", result)

    def test_fix_unknown_severity(self):
        finding = json.dumps({
            "file": "test.py",
            "line": 1,
            "severity": "unknown_sev",
            "message": "m",
            "rule_id": "r",
        })
        result = asyncio.run(self.handler(f"fix {finding}"))
        self.assertIn("Fix proposal", result)

    def test_post_no_proposals(self):
        result = asyncio.run(self.handler("post --dry-run"))
        self.assertIn("No proposals", result)


class TestSessionTagsHandler(unittest.TestCase):
    def setUp(self):
        # Reset state between tests
        import lidco.cli.commands.q113_cmds as mod
        mod._state.clear()
        self.cmds = _make_registry()
        self.handler = self.cmds["session-tags"].handler

    def test_usage_no_args(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_tag_missing_args(self):
        result = asyncio.run(self.handler("tag"))
        self.assertIn("Usage", result)

    def test_tag_session(self):
        result = asyncio.run(self.handler("tag session1 bugbot,review"))
        self.assertIn("Tagged", result)
        self.assertIn("session1", result)

    def test_search_no_query(self):
        result = asyncio.run(self.handler("search"))
        self.assertIn("Usage", result)

    def test_search_no_results(self):
        result = asyncio.run(self.handler("search nonexistent"))
        self.assertIn("No sessions", result)

    def test_search_with_results(self):
        asyncio.run(self.handler("tag s1 bugbot,test"))
        result = asyncio.run(self.handler("search bugbot"))
        self.assertIn("s1", result)

    def test_list_empty(self):
        result = asyncio.run(self.handler("list"))
        self.assertIn("No tagged", result)

    def test_list_with_sessions(self):
        asyncio.run(self.handler("tag s1 a,b"))
        asyncio.run(self.handler("tag s2 c"))
        result = asyncio.run(self.handler("list"))
        self.assertIn("s1", result)
        self.assertIn("s2", result)

    def test_tag_multiple_tags(self):
        asyncio.run(self.handler("tag s1 a,b,c"))
        result = asyncio.run(self.handler("search a"))
        self.assertIn("s1", result)

    def test_tag_then_list(self):
        asyncio.run(self.handler("tag s1 t1"))
        result = asyncio.run(self.handler("list"))
        self.assertIn("1 tagged", result)


class TestLintHookHandler(unittest.TestCase):
    def setUp(self):
        import lidco.cli.commands.q113_cmds as mod
        mod._state.clear()
        self.cmds = _make_registry()
        self.handler = self.cmds["lint-hook"].handler

    def test_usage_no_args(self):
        result = asyncio.run(self.handler(""))
        self.assertIn("Usage", result)

    def test_enable(self):
        result = asyncio.run(self.handler("enable"))
        self.assertIn("enabled", result.lower())

    def test_disable(self):
        result = asyncio.run(self.handler("disable"))
        self.assertIn("disabled", result.lower())

    def test_status_default_enabled(self):
        result = asyncio.run(self.handler("status"))
        self.assertIn("enabled", result.lower())

    def test_disable_then_status(self):
        asyncio.run(self.handler("disable"))
        result = asyncio.run(self.handler("status"))
        self.assertIn("disabled", result.lower())

    def test_enable_after_disable(self):
        asyncio.run(self.handler("disable"))
        asyncio.run(self.handler("enable"))
        result = asyncio.run(self.handler("status"))
        self.assertIn("enabled", result.lower())


if __name__ == "__main__":
    unittest.main()
