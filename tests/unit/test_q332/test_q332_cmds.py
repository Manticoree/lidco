"""Tests for CLI commands q332_cmds (Q332, task 1776)."""
from __future__ import annotations

import asyncio
import unittest


class _FakeRegistry:
    """Minimal registry stub for testing command registration."""

    def __init__(self) -> None:
        self.commands: dict[str, tuple[str, object]] = {}

    def register_async(self, name: str, description: str, handler: object) -> None:
        self.commands[name] = (description, handler)


def _run(coro):
    return asyncio.run(coro)


class TestRegisterQ332Commands(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q332_cmds import register_q332_commands
        self.reg = _FakeRegistry()
        register_q332_commands(self.reg)

    def test_commands_registered(self) -> None:
        self.assertIn("review-patterns", self.reg.commands)
        self.assertIn("review-train", self.reg.commands)
        self.assertIn("review-style", self.reg.commands)
        self.assertIn("review-analytics", self.reg.commands)


class TestReviewPatternsHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q332_cmds import register_q332_commands
        self.reg = _FakeRegistry()
        register_q332_commands(self.reg)
        self.handler = self.reg.commands["review-patterns"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_list_all(self) -> None:
        result = _run(self.handler("list"))
        self.assertIn("Review Patterns", result)

    def test_list_by_category(self) -> None:
        result = _run(self.handler("list category security"))
        self.assertIn("critical", result.lower())

    def test_list_bad_category(self) -> None:
        result = _run(self.handler("list category nope"))
        self.assertIn("Unknown category", result)

    def test_list_by_language(self) -> None:
        result = _run(self.handler("list language python"))
        self.assertIn("Patterns", result)

    def test_list_bad_filter(self) -> None:
        result = _run(self.handler("list badfilter val"))
        self.assertIn("Unknown filter", result)

    def test_show(self) -> None:
        result = _run(self.handler("show magic-number"))
        self.assertIn("magic-number", result)

    def test_show_not_found(self) -> None:
        result = _run(self.handler("show nonexistent"))
        self.assertIn("not found", result)

    def test_show_missing_arg(self) -> None:
        result = _run(self.handler("show"))
        self.assertIn("Usage", result)

    def test_search(self) -> None:
        result = _run(self.handler("search magic"))
        self.assertIn("magic-number", result)

    def test_search_no_results(self) -> None:
        result = _run(self.handler("search zzzznothing"))
        self.assertIn("No patterns", result)

    def test_add(self) -> None:
        result = _run(self.handler("add test-p desc anti_pattern error"))
        self.assertIn("Added pattern", result)

    def test_add_bad_severity(self) -> None:
        result = _run(self.handler("add test-p desc anti_pattern badval"))
        self.assertIn("Invalid", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self.handler("foobar"))
        self.assertIn("Unknown subcommand", result)


class TestReviewTrainHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q332_cmds import register_q332_commands
        self.reg = _FakeRegistry()
        register_q332_commands(self.reg)
        self.handler = self.reg.commands["review-train"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_list(self) -> None:
        result = _run(self.handler("list"))
        self.assertIn("Sample PRs", result)

    def test_list_difficulty(self) -> None:
        result = _run(self.handler("list beginner"))
        self.assertIn("Sample PRs", result)

    def test_list_bad_difficulty(self) -> None:
        result = _run(self.handler("list extreme"))
        self.assertIn("Unknown difficulty", result)

    def test_start(self) -> None:
        result = _run(self.handler("start sample-001"))
        self.assertIn("Add user authentication", result)

    def test_start_not_found(self) -> None:
        result = _run(self.handler("start nope"))
        self.assertIn("not found", result)

    def test_hints(self) -> None:
        result = _run(self.handler("hints sample-001"))
        self.assertIn("Hints", result)

    def test_hints_not_found(self) -> None:
        result = _run(self.handler("hints nope"))
        self.assertIn("No hints", result)

    def test_submit(self) -> None:
        result = _run(self.handler('submit sample-001 "hardcoded secret" "broad except"'))
        self.assertIn("Score", result)

    def test_submit_unknown_pr(self) -> None:
        result = _run(self.handler("submit nope issue1"))
        self.assertIn("Error", result)

    def test_scores_empty(self) -> None:
        result = _run(self.handler("scores"))
        self.assertIn("No scores", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self.handler("foobar"))
        self.assertIn("Unknown subcommand", result)


class TestReviewStyleHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q332_cmds import register_q332_commands
        self.reg = _FakeRegistry()
        register_q332_commands(self.reg)
        self.handler = self.reg.commands["review-style"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_conventions(self) -> None:
        result = _run(self.handler("conventions"))
        self.assertIn("Review Conventions", result)
        self.assertIn("be-constructive", result)

    def test_templates(self) -> None:
        result = _run(self.handler("templates"))
        self.assertIn("Feedback Templates", result)

    def test_templates_filter(self) -> None:
        result = _run(self.handler("templates security"))
        self.assertIn("security-concern", result)

    def test_render(self) -> None:
        result = _run(self.handler("render suggest-refactor code=loop target=function"))
        self.assertIn("loop", result)
        self.assertIn("function", result)

    def test_render_not_found(self) -> None:
        result = _run(self.handler("render nonexistent"))
        self.assertIn("not found", result)

    def test_add_convention(self) -> None:
        result = _run(self.handler("add-convention myconv 'My description'"))
        self.assertIn("Added convention", result)

    def test_add_template(self) -> None:
        result = _run(self.handler("add-template tid cat neutral 'some template'"))
        self.assertIn("Added template", result)

    def test_add_template_bad_tone(self) -> None:
        result = _run(self.handler("add-template tid cat badtone tpl"))
        self.assertIn("Unknown tone", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self.handler("foobar"))
        self.assertIn("Unknown subcommand", result)


class TestReviewAnalyticsHandler(unittest.TestCase):
    def setUp(self) -> None:
        from lidco.cli.commands.q332_cmds import register_q332_commands
        self.reg = _FakeRegistry()
        register_q332_commands(self.reg)
        self.handler = self.reg.commands["review-analytics"][1]

    def test_no_args_shows_usage(self) -> None:
        result = _run(self.handler(""))
        self.assertIn("Usage", result)

    def test_summary(self) -> None:
        result = _run(self.handler("summary"))
        self.assertIn("Review Analytics Summary", result)

    def test_reviewer_no_data(self) -> None:
        result = _run(self.handler("reviewer alice"))
        self.assertIn("No data", result)

    def test_issues_empty(self) -> None:
        result = _run(self.handler("issues"))
        self.assertIn("No issues", result)

    def test_trend_empty(self) -> None:
        result = _run(self.handler("trend"))
        self.assertIn("No trend", result)

    def test_unknown_subcmd(self) -> None:
        result = _run(self.handler("foobar"))
        self.assertIn("Unknown subcommand", result)


if __name__ == "__main__":
    unittest.main()
