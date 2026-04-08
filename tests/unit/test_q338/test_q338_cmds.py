"""Tests for Q338 CLI commands (Task 1806)."""
from __future__ import annotations

import asyncio
import unittest


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self):
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler) -> None:
        self.commands[name] = (description, handler)


def _run(coro):
    return asyncio.run(coro)


class TestQ338Registration(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q338_cmds import register_q338_commands
        self.reg = _FakeRegistry()
        register_q338_commands(self.reg)

    def test_all_commands_registered(self):
        expected = {"marketplace-v2", "theme-gallery", "share-recipe", "community"}
        self.assertEqual(set(self.reg.commands.keys()), expected)


class TestMarketplaceV2Cmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q338_cmds import register_q338_commands
        self.reg = _FakeRegistry()
        register_q338_commands(self.reg)
        self.handler = self.reg.commands["marketplace-v2"][1]

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_browse_empty(self):
        result = _run(self.handler("browse"))
        self.assertIn("No plugins", result)

    def test_search_no_query(self):
        result = _run(self.handler("search"))
        self.assertIn("Usage", result)

    def test_publish_no_json(self):
        result = _run(self.handler("publish"))
        self.assertIn("Usage", result)

    def test_publish_invalid_json(self):
        result = _run(self.handler("publish not-json"))
        self.assertIn("Error", result)

    def test_publish_valid(self):
        import json
        data = json.dumps({"name": "test", "author": "alice"})
        result = _run(self.handler(f"publish {data}"))
        self.assertIn("Published", result)
        self.assertIn("test", result)

    def test_review_missing_args(self):
        result = _run(self.handler("review"))
        self.assertIn("Usage", result)

    def test_review_invalid_rating(self):
        result = _run(self.handler("review myplugin abc"))
        self.assertIn("Rating must be", result)

    def test_download_missing(self):
        result = _run(self.handler("download"))
        self.assertIn("Usage", result)

    def test_update_check_missing(self):
        result = _run(self.handler("update-check"))
        self.assertIn("Usage", result)

    def test_compat_missing(self):
        result = _run(self.handler("compat"))
        self.assertIn("Usage", result)

    def test_stats(self):
        result = _run(self.handler("stats"))
        self.assertIn("Marketplace stats", result)

    def test_unknown_subcmd(self):
        result = _run(self.handler("nope"))
        self.assertIn("Unknown", result)


class TestThemeGalleryCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q338_cmds import register_q338_commands
        self.reg = _FakeRegistry()
        register_q338_commands(self.reg)
        self.handler = self.reg.commands["theme-gallery"][1]

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_browse_empty(self):
        result = _run(self.handler("browse"))
        self.assertIn("No themes", result)

    def test_search_no_query(self):
        result = _run(self.handler("search"))
        self.assertIn("Usage", result)

    def test_add_no_json(self):
        result = _run(self.handler("add"))
        self.assertIn("Usage", result)

    def test_add_valid(self):
        import json
        data = json.dumps({"name": "ocean", "author": "alice"})
        result = _run(self.handler(f"add {data}"))
        self.assertIn("Added theme", result)

    def test_install_missing(self):
        result = _run(self.handler("install"))
        self.assertIn("Usage", result)

    def test_rate_missing(self):
        result = _run(self.handler("rate"))
        self.assertIn("Usage", result)

    def test_rate_invalid_score(self):
        result = _run(self.handler("rate mytheme abc"))
        self.assertIn("Score must be", result)

    def test_preview_missing(self):
        result = _run(self.handler("preview"))
        self.assertIn("Usage", result)

    def test_trending_empty(self):
        result = _run(self.handler("trending"))
        self.assertIn("No trending", result)

    def test_seasonal_missing(self):
        result = _run(self.handler("seasonal"))
        self.assertIn("Usage", result)

    def test_seasonal_invalid(self):
        result = _run(self.handler("seasonal invalid"))
        self.assertIn("Invalid season", result)

    def test_stats(self):
        result = _run(self.handler("stats"))
        self.assertIn("Gallery stats", result)

    def test_unknown_subcmd(self):
        result = _run(self.handler("nope"))
        self.assertIn("Unknown", result)


class TestShareRecipeCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q338_cmds import register_q338_commands
        self.reg = _FakeRegistry()
        register_q338_commands(self.reg)
        self.handler = self.reg.commands["share-recipe"][1]

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_browse_empty(self):
        result = _run(self.handler("browse"))
        self.assertIn("No recipes", result)

    def test_search_no_query(self):
        result = _run(self.handler("search"))
        self.assertIn("Usage", result)

    def test_publish_no_json(self):
        result = _run(self.handler("publish"))
        self.assertIn("Usage", result)

    def test_publish_valid(self):
        import json
        data = json.dumps({"name": "auto-lint", "author": "alice", "steps": [{"name": "lint", "action": "run"}]})
        result = _run(self.handler(f"publish {data}"))
        self.assertIn("Published recipe", result)

    def test_fork_missing(self):
        result = _run(self.handler("fork"))
        self.assertIn("Usage", result)

    def test_rate_missing(self):
        result = _run(self.handler("rate"))
        self.assertIn("Usage", result)

    def test_rate_invalid_score(self):
        result = _run(self.handler("rate abc xyz"))
        self.assertIn("Score must be", result)

    def test_download_missing(self):
        result = _run(self.handler("download"))
        self.assertIn("Usage", result)

    def test_stats(self):
        result = _run(self.handler("stats"))
        self.assertIn("Recipe store stats", result)

    def test_unknown_subcmd(self):
        result = _run(self.handler("nope"))
        self.assertIn("Unknown", result)


class TestCommunityCmd(unittest.TestCase):
    def setUp(self):
        from lidco.cli.commands.q338_cmds import register_q338_commands
        self.reg = _FakeRegistry()
        register_q338_commands(self.reg)
        self.handler = self.reg.commands["community"][1]

    def test_no_args(self):
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_stats(self):
        result = _run(self.handler("stats"))
        self.assertIn("Community stats", result)

    def test_activity_empty(self):
        result = _run(self.handler("activity"))
        self.assertIn("No recent activity", result)

    def test_leaderboard_empty(self):
        result = _run(self.handler("leaderboard"))
        self.assertIn("No contributors", result)

    def test_contributor_missing(self):
        result = _run(self.handler("contributor"))
        self.assertIn("Usage", result)

    def test_contributor_not_found(self):
        result = _run(self.handler("contributor nobody"))
        self.assertIn("not found", result)

    def test_unknown_subcmd(self):
        result = _run(self.handler("nope"))
        self.assertIn("Unknown", result)


if __name__ == "__main__":
    unittest.main()
