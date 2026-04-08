"""Tests for lidco.cli.commands.q335_cmds — Q335 CLI commands."""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = handler


def _run(coro):
    return asyncio.run(coro)


class TestRegisterQ335Commands(unittest.TestCase):
    """Tests that all Q335 commands are registered."""

    def setUp(self) -> None:
        from lidco.cli.commands.q335_cmds import register_q335_commands
        self.registry = _FakeRegistry()
        register_q335_commands(self.registry)

    def test_commands_registered(self) -> None:
        self.assertIn("mentor", self.registry.commands)
        self.assertIn("pair-ai", self.registry.commands)
        self.assertIn("walkthrough", self.registry.commands)
        self.assertIn("gen-feedback", self.registry.commands)

    def test_four_commands(self) -> None:
        self.assertEqual(len(self.registry.commands), 4)


class TestMentorHandler(unittest.TestCase):
    """Tests for /mentor command."""

    def setUp(self) -> None:
        from lidco.cli.commands.q335_cmds import register_q335_commands
        self.registry = _FakeRegistry()
        register_q335_commands(self.registry)
        self.handler = self.registry.commands["mentor"]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_add_profile(self) -> None:
        data = json.dumps({"user_id": "u1", "name": "Alice", "is_mentor": True, "skills": [{"name": "python", "level": 5}]})
        result = _run(self.handler(f"add {data}"))
        self.assertIn("Added profile", result)

    def test_add_invalid_json(self) -> None:
        result = _run(self.handler("add {invalid"))
        self.assertIn("Error", result)

    def test_add_missing_args(self) -> None:
        result = _run(self.handler("add"))
        self.assertIn("Usage", result)

    def test_list(self) -> None:
        result = _run(self.handler("list"))
        self.assertIn("Profiles", result)

    def test_match(self) -> None:
        result = _run(self.handler("match e1"))
        self.assertIn("matches", result.lower())

    def test_match_missing_args(self) -> None:
        result = _run(self.handler("match"))
        self.assertIn("Usage", result)

    def test_remove(self) -> None:
        result = _run(self.handler("remove u1"))
        self.assertIn("Removed", result)

    def test_remove_missing_args(self) -> None:
        result = _run(self.handler("remove"))
        self.assertIn("Usage", result)

    def test_profile(self) -> None:
        result = _run(self.handler("profile u1"))
        self.assertIn("Profile", result)

    def test_profile_missing_args(self) -> None:
        result = _run(self.handler("profile"))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self) -> None:
        result = _run(self.handler("xyz"))
        self.assertIn("Unknown", result)


class TestPairAiHandler(unittest.TestCase):
    """Tests for /pair-ai command."""

    def setUp(self) -> None:
        from lidco.cli.commands.q335_cmds import register_q335_commands
        self.registry = _FakeRegistry()
        register_q335_commands(self.registry)
        self.handler = self.registry.commands["pair-ai"]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_start(self) -> None:
        result = _run(self.handler("start"))
        self.assertIn("session started", result.lower())

    def test_start_with_difficulty(self) -> None:
        result = _run(self.handler("start beginner"))
        self.assertIn("beginner", result.lower())

    def test_explain(self) -> None:
        result = _run(self.handler("explain decorator"))
        self.assertIn("decorator", result.lower())

    def test_explain_missing_args(self) -> None:
        result = _run(self.handler("explain"))
        self.assertIn("Usage", result)

    def test_suggest(self) -> None:
        result = _run(self.handler("suggest x = 1"))
        self.assertIn("Alternative", result)

    def test_suggest_missing_args(self) -> None:
        result = _run(self.handler("suggest"))
        self.assertIn("Usage", result)

    def test_practices(self) -> None:
        result = _run(self.handler("practices"))
        self.assertIn("Best Practices", result)

    def test_practices_filtered(self) -> None:
        result = _run(self.handler("practices early_return"))
        self.assertIn("early_return", result)

    def test_practices_no_match(self) -> None:
        result = _run(self.handler("practices nonexistent_xyz"))
        self.assertIn("No matching", result)

    def test_end(self) -> None:
        result = _run(self.handler("end pair-1"))
        self.assertIn("Ended", result)

    def test_end_missing_args(self) -> None:
        result = _run(self.handler("end"))
        self.assertIn("Usage", result)

    def test_unknown_subcommand(self) -> None:
        result = _run(self.handler("xyz"))
        self.assertIn("Unknown", result)


class TestWalkthroughHandler(unittest.TestCase):
    """Tests for /walkthrough command."""

    def setUp(self) -> None:
        from lidco.cli.commands.q335_cmds import register_q335_commands
        self.registry = _FakeRegistry()
        register_q335_commands(self.registry)
        self.handler = self.registry.commands["walkthrough"]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_create(self) -> None:
        result = _run(self.handler("create MyWalk"))
        self.assertIn("Created", result)

    def test_create_missing_args(self) -> None:
        result = _run(self.handler("create"))
        self.assertIn("Usage", result)

    def test_add_step(self) -> None:
        result = _run(self.handler('add-step wt-1 "Step 1" "Description"'))
        self.assertIn("Added step", result)

    def test_add_step_missing_args(self) -> None:
        result = _run(self.handler("add-step wt-1"))
        self.assertIn("Usage", result)

    def test_next(self) -> None:
        result = _run(self.handler("next wt-1"))
        self.assertIn("Advanced", result)

    def test_next_missing_args(self) -> None:
        result = _run(self.handler("next"))
        self.assertIn("Usage", result)

    def test_back(self) -> None:
        result = _run(self.handler("back wt-1"))
        self.assertIn("back", result.lower())

    def test_back_missing_args(self) -> None:
        result = _run(self.handler("back"))
        self.assertIn("Usage", result)

    def test_bookmark(self) -> None:
        result = _run(self.handler("bookmark wt-1 important main.py 1 10"))
        self.assertIn("Bookmarked", result)

    def test_bookmark_missing_args(self) -> None:
        result = _run(self.handler("bookmark wt-1 label"))
        self.assertIn("Usage", result)

    def test_show(self) -> None:
        result = _run(self.handler("show wt-1"))
        self.assertIn("Walkthrough", result)

    def test_show_missing_args(self) -> None:
        result = _run(self.handler("show"))
        self.assertIn("Usage", result)

    def test_list(self) -> None:
        result = _run(self.handler("list"))
        self.assertIn("Walkthroughs", result)

    def test_unknown_subcommand(self) -> None:
        result = _run(self.handler("xyz"))
        self.assertIn("Unknown", result)


class TestGenFeedbackHandler(unittest.TestCase):
    """Tests for /gen-feedback command."""

    def setUp(self) -> None:
        from lidco.cli.commands.q335_cmds import register_q335_commands
        self.registry = _FakeRegistry()
        register_q335_commands(self.registry)
        self.handler = self.registry.commands["gen-feedback"]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_analyze_inline(self) -> None:
        result = _run(self.handler("def foo(): pass"))
        self.assertIn("Score", result)

    def test_file_missing_args(self) -> None:
        result = _run(self.handler("file"))
        self.assertIn("Usage", result)

    def test_file_nonexistent(self) -> None:
        result = _run(self.handler("file /nonexistent/path/xyz.py"))
        self.assertIn("Error", result)

    def test_add_check(self) -> None:
        result = _run(self.handler("add-check fixme FIXME found_fixme"))
        self.assertIn("Added check", result)

    def test_add_check_missing_args(self) -> None:
        result = _run(self.handler("add-check name"))
        self.assertIn("Usage", result)

    def test_remove_check(self) -> None:
        result = _run(self.handler("remove-check print_statement"))
        self.assertIn("Removed", result)

    def test_remove_check_nonexistent(self) -> None:
        result = _run(self.handler("remove-check nonexistent"))
        self.assertIn("not found", result)

    def test_remove_check_missing_args(self) -> None:
        result = _run(self.handler("remove-check"))
        self.assertIn("Usage", result)


if __name__ == "__main__":
    unittest.main()
